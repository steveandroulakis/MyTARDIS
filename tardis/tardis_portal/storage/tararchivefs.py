import tarfile
import uuid
from celery.task import task
from django.db import transaction
import os
import errno
from datetime import datetime

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files import locks, File
from django.core.files.move import file_move_safe
from django.utils.crypto import get_random_string
from django.utils.encoding import force_text, filepath_to_uri
from django.utils.functional import LazyObject
from django.utils.module_loading import import_by_path
from django.utils.text import get_valid_filename
from django.utils._os import safe_join, abspathu
from django.core.files.storage import Storage
import logging
import shutil
from tardis.tardis_portal.models import DataFile, StorageBox, StorageBoxOption, Dataset, DataFileObject

log = logging.getLogger(__name__)


class TarArchiveFileSystemStorage(Storage):
    """
    Tar Archive storage
    """

    def __init__(self, base_url=None, dataset_id=None, cache_status=None):

        self.tar_path = getattr(settings,
                                   'TARARCHIVE_TAR_PATH',
                                   '/mnt/tararchive')

        self.cache_path = getattr(settings,
                                  'TARARCHIVE_CACHE_PATH',
                                  '/mnt/tararchive_cache')

        self.base_location = self.cache_path
        if base_url is None:
            base_url = settings.MEDIA_URL
        self.base_url = base_url
        self.dataset_id = dataset_id
        self.cache_status = cache_status
        tararchive_util = TarArchiveFileSystemStorageUtil(self.dataset_id)

        self.tar_file, self.cache_file = tararchive_util.archive_paths()


    '''
    In reality this won't happen from direct downloads as we don't want to
    bring back an entire tar file in a blocking fashion for the user.

    Instead we'll present a 'please wait for an email when the tar is back'
    email and set off a task to grab the tar.

    However, this function will probably help a copy() action back to default
    storage as part of a mass extraction.

    Eg. iterate dfos in tararchive storage box, extract to cache location,
    then copy to default storage box or anywhere.

    Cleanup from cache location would then occur.

    Files must be written to cache location or *somewhere* first because
    the tar extraction process doesn't return a 'real' file handle so
    breaks the django-storage abstraction.
    '''
    def _open(self, name, mode='rb'):
        import tarfile, shutil

        tar_name, filename = file_archive_paths(name)

        # open tar in cache for reading
        tar = tarfile.open(self.cache_file)

        write_path = self.cache_path + '/' + filename

        member = tar.getmember(filename)

        f = tar.extractfile(member)

        ensure_dir(write_path)

        with open(write_path, 'w+') as extracted_file:
            extracted_file.write(f.read())

        tar.close()
        return File(open(write_path, mode))

    def _save(self, name, content):
        full_path = self.path(name)

        # Create any intermediate directories that do not exist.
        # Note that there is a race between os.path.exists and os.makedirs:
        # if os.makedirs fails with EEXIST, the directory was created
        # concurrently, and we can continue normally. Refs #16082.
        directory = os.path.dirname(full_path)
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
        if not os.path.isdir(directory):
            raise IOError("%s exists and is not a directory." % directory)

        # There's a potential race condition between get_available_name and
        # saving the file; it's possible that two threads might return the
        # same name, at which point all sorts of fun happens. So we need to
        # try to create the file, but if it already exists we have to go back
        # to get_available_name() and try again.

        while True:
            try:
                # This file has a file path that we can move.
                if hasattr(content, 'temporary_file_path'):
                    file_move_safe(content.temporary_file_path(), full_path)
                    content.close()

                # This is a normal uploadedfile that we can stream.
                else:
                    # This fun binary flag incantation makes os.open throw an
                    # OSError if the file already exists before we open it.
                    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, 'O_BINARY', 0))
                    # The current umask value is masked out by os.open!
                    fd = os.open(full_path, flags, 0o666)
                    _file = None
                    try:
                        locks.lock(fd, locks.LOCK_EX)
                        for chunk in content.chunks():
                            if _file is None:
                                mode = 'wb' if isinstance(chunk, bytes) else 'wt'
                                _file = os.fdopen(fd, mode)
                            _file.write(chunk)
                    finally:
                        locks.unlock(fd)
                        if _file is not None:
                            _file.close()
                        else:
                            os.close(fd)
            except OSError as e:
                if e.errno == errno.EEXIST:
                    # Ooops, the file exists. We need a new file name.
                    name = self.get_available_name(name)
                    full_path = self.path(name)
                else:
                    raise
            else:
                # OK, the file save worked. Break out of the loop.
                break

        if settings.FILE_UPLOAD_PERMISSIONS is not None:
            os.chmod(full_path, settings.FILE_UPLOAD_PERMISSIONS)

        return name

    def delete(self, name):
        """
        Deletes the specified file from the storage system.
        """
        raise NotImplementedError("This backend doesn't support deletion.")

    def exists(self, name):
        tar_file, filename = file_archive_paths(name)
        return os.path.exists(self.path(filename))

    def listdir(self, path):
        path = self.path(path)
        directories, files = [], []
        for entry in os.listdir(path):
            if os.path.isdir(os.path.join(path, entry)):
                directories.append(entry)
            else:
                files.append(entry)
        return directories, files

    def path(self, name):
        try:
            path = safe_join(self.location, name)
        except ValueError:
            raise SuspiciousFileOperation("Attempted access to '%s' denied." % name)
        return os.path.normpath(path)

    def size(self, name):
        return os.path.getsize(self.path(name))

    def accessed_time(self, name):
        return datetime.fromtimestamp(os.path.getatime(self.path(name)))

    def created_time(self, name):
        return datetime.fromtimestamp(os.path.getctime(self.path(name)))

    def modified_time(self, name):
        return datetime.fromtimestamp(os.path.getmtime(self.path(name)))


class TarArchiveFileSystemStorageUtil():
    """
    Tar Archive storage
    """

    def __init__(self, dataset_id=None):

        self.dataset_id = dataset_id

        self.tar_path = getattr(settings,
                                   'TARARCHIVE_TAR_PATH',
                                   '/mnt/tararchive')

        self.cache_path = getattr(settings,
                                  'TARARCHIVE_CACHE_PATH',
                                  '/mnt/tararchive_cache')

    def archive_paths(self):
        tar_file = os.path.join(self.tar_path, '%s%s' % (self.dataset_id, '.tar'))
        cache_file = os.path.join(self.cache_path, '%s%s' % (self.dataset_id, '.tar'))

        return tar_file, cache_file

    def newer_archive(self):

        tar_file, cache_file = self.archive_paths(self.dataset_id)

        # if true then need to get from tape
        if not os.path.exists(cache_file):
            log.info('path %s does not exist' % cache_file)
            return True

        not_modified = \
            os.path.getmtime(tar_file) == os.path.getmtime(cache_file)
        print not_modified

        return not not_modified

    def is_tape_only(self):
        dfs = DataFile.objects.filter(dataset__id=self.dataset_id, \
        file_objects__storage_box__django_storage_class=
            settings.TARARCHIVE_CLASS)

        tape_only = True

        if len(dfs) == 0:
            tape_only = False

        for df in dfs:
            if df.file_objects.count() > 1:
                tape_only = False

        return tape_only

@task
def retrieve_dfos_from_tararchive(dataset_id):
        tararchive_util = TarArchiveFileSystemStorageUtil(dataset_id)

        tararchive_box = \
            StorageBox.objects.filter(options__key='dataset_id',
                                      options__value=dataset_id,
                                      django_storage_class=
                                      settings.TARARCHIVE_CLASS).first()

        if tararchive_box is None:
            print "dataset %s has no data on tar archive" % dataset_id
            return

        retrieval_status = tararchive_box.get_options_as_dict()['cache_status']
        if retrieval_status == "pending":
            print "task cancelled: action in progress"
            return

        update_cache_status(tararchive_box, 'pending')
        print 'Tape only dataset: ' + str(tararchive_util.is_tape_only())

        if tararchive_util.is_tape_only():

            print 'getting data from tape as its different from archived'
            retrieve_tar_from_tape(dataset_id)
            # print 'copying files back to default box'

            tararchive_box.copy_files()

        update_cache_status(tararchive_box, 'cached')


def retrieve_tar_from_tape(dataset_id):
    import time

    tararchive_util = TarArchiveFileSystemStorageUtil(dataset_id)
    tar_file, cache_file = tararchive_util.archive_paths()
    # tmp tar in cache for extract
    time.sleep(2)
    shutil.copy2(tar_file, cache_file)
    time.sleep(2)

    return cache_file


def update_cache_status(tararchive_box, value):
    key = 'cache_status'
    try:
        opt = tararchive_box.options.get(key=key)
        opt.value = value
        opt.save()
    except StorageBoxOption.DoesNotExist:
        opt = StorageBoxOption(storage_box=tararchive_box, key=key, value=value)
        opt.save()


def ensure_dir(f):
    '''
    mkdir -p
    '''
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)


def file_archive_paths(filename):
    '''
    returns ('1.tar', 'Test Dataset-1/file.png')
    from filename '1.tar/Test Dataset-1/file.png'
    '''
    tar_name = filename.split('/')[0]
    file_path = filename[len(tar_name) + 1:]
    return tar_name, file_path


def get_or_create_tararchive_box(dataset_id):
    tararchive_box = tararchive_boxes = StorageBox.objects.filter(
        options__key='dataset_id', options__value=dataset_id,
        django_storage_class=settings.TARARCHIVE_CLASS).first()

    if not tararchive_box:
        print "creating tararchive_box for %s" % dataset_id

        tararchive_box = StorageBox(django_storage_class=settings.TARARCHIVE_CLASS,
                                   max_size=settings.TARARCHIVE_MAX_CACHE_SIZE,
                                   status='online',
                                   name='tararchive dataset %s' % dataset_id,
                                   description='tararchive storage')
        tararchive_box.save()
        opt = StorageBoxOption(storage_box=tararchive_box, key='dataset_id', value=str(dataset_id))
        opt.save()
        opt = StorageBoxOption(storage_box=tararchive_box, key='cache_status', value='none')
        opt.save()
    else:
        print "tararchive box for dataset %s - exists" % dataset_id

    return tararchive_box


def can_tar_archive(tararchive_box, dataset_id):
    retrieval_status = tararchive_box.get_options_as_dict()['cache_status']
    if retrieval_status == "pending":
        print "task cancelled: action in progress"
        return False

    # dfos for dataset with default boxes but nothing else
    dfs = DataFile.objects.filter(dataset__id=dataset_id,
                                  file_objects__storage_box=\
                                  tararchive_box.get_default_storage())

    no_disk = (dfs.count() == 0)
    if no_disk:
        print 'Not archiving dataset %s - No disk copy' % dataset_id
        return False

    return True


def tararchive_datasets():
    datasets = Dataset.objects.all()

    for dataset in datasets:
        tararchive_box = get_or_create_tararchive_box(dataset.id)

        can_tar = can_tar_archive(tararchive_box, dataset.id)
        print "can tar archive dataset %s - %s"\
        % (dataset.id, can_tar)

        if can_tar:
            tararchive_dataset(dataset.id)


def tararchive_dataset(dataset_id):
    dataset = Dataset.objects.get(id=dataset_id)
    print 'dataset: ' + str(dataset)

    tararchive_box = StorageBox.objects.filter(
        options__key='dataset_id', options__value=dataset_id,
        django_storage_class=settings.TARARCHIVE_CLASS).first()

    tararchive_util = TarArchiveFileSystemStorageUtil(dataset_id)

    dataset_tar, existing_cache_tar = tararchive_util.archive_paths()

    update_cache_status(tararchive_box, 'pending')

    # remove all old associated dfos from box
    for dfo in tararchive_box.file_objects.all():
        print dfo
        print file_archive_paths(dfo.file_object.name)
        dfo.delete()

    # tar exists or not
    exists = os.path.isfile(dataset_tar)
    print 'tar exists: ' + str(exists)

    unique_filename = str(uuid.uuid4()) + '.tar'
    tmp_cache_tar = os.path.dirname(existing_cache_tar)\
        + '/' + unique_filename

    # if tar archive doesn't exist
    # TODOsteve modified times and update/replace tar
    if 1==1:
        # create tar in cache
        with tarfile.open(tmp_cache_tar, "w") as tar:
            for df in dataset.datafile_set.all():

                dfo = df.file_objects.first()
                file_path = dfo._storage.path(dfo.uri)

                info = tarfile.TarInfo(name=dfo.uri)
                info.size=os.path.getsize(file_path)

                # todo: file object not file path
                # eg to be swift compatible?
                tar.addfile(info,
                        file(file_path))

        # copy file to tar archive and rename to dataset_id.tar
        existing_cache_tar

        print 'renaming ' + str(tmp_cache_tar) \
            + ' to ' + str(existing_cache_tar)
        os.rename(tmp_cache_tar, existing_cache_tar)

        print 'copying temp tar file ' + tmp_cache_tar + ' to ' + os.path.dirname(dataset_tar)
        shutil.copy2(existing_cache_tar, dataset_tar)

        # remove tar from cache
        #os.remove(tmp_cache_tar)

        for df in dataset.datafile_set.all():
            dfo = df.file_objects.first()
            print '\t' + dfo._storage.path(dfo.uri)

            # create dfo
            # TODOsteve create storage box in process
            copy = DataFileObject(
                datafile=df,
                storage_box=tararchive_box,
                uri='%s.tar/%s' % (dataset_id, dfo.uri))
            copy.save()

            print 'creating dfo copy ' + str(df) + ' in ' + str(tararchive_box)

        update_cache_status(tararchive_box, 'stored')

    # TODOsteve finally clean up on fail/success