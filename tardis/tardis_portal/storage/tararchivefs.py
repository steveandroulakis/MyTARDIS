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
from tardis.tardis_portal.models import StorageBox, DataFileObject

log = logging.getLogger(__name__)

@task(name="tardis_portal.tararchive.copy_files", ignore_result=True)
def copy_files(self, dest_box=None):
    for dfo in self.file_objects.all():
        dfo.copy_file(dest_box)


@task(name='tardis_portal.tararchive.copy_file', ignore_result=True)
def copy_file(self, dest_box=None, verify=True):
    '''
    copies file to new storage box
    checks for existing copy
    triggers async verification if not disabled
    '''
    if dest_box is None:
        dest_box = StorageBox.get_default_storage()
    existing = self.datafile.file_objects.filter(storage_box=dest_box)
    if existing.count() > 0:
        if not existing[0].verified and verify:
            existing[0].verify.delay()
        return existing[0]
    try:
        with transaction.commit_on_success():
            copy = DataFileObject(
                datafile=self.datafile,
                storage_box=dest_box)
            copy.save()
            copy.file_object = self.file_object
    except Exception as e:
        log.error(
            'file move failed for dfo id: %s, with error: %s' %
            (self.id, str(e)))
        return False
    if verify:
        copy.verify.delay()
    return copy

#TODOsteve utils
def ensure_dir(f):
    d = os.path.dirname(f)
    if not os.path.exists(d):
        os.makedirs(d)

def newer_archive(tar_file, cache_file):
    # if true then need to get from tape
    if not os.path.exists(cache_file):
        print 'path %s does not exist' % cache_file
        return True

    print tar_file
    print cache_file
    not_modified = \
        os.path.getmtime(tar_file) == os.path.getmtime(cache_file)
    print not_modified

    return not not_modified


def retrieve_tar_from_tape(tar_path, cache_path, dataset_id):
    import shutil
    tar_file = tar_path + '/' + dataset_id + '.tar'
    cache_file = cache_path + '/' + dataset_id + '.tar'
    # tmp tar in cache for extract
    shutil.copy2(tar_file, cache_file)

    return cache_file


# todo add functions to
class TarArchiveFileSystemStorage(Storage):
    """
    Standard filesystem storage
    """

    def __init__(self, cache_path=None, base_url=None, dataset_id=None,
                 tar_path=None):
        # cache location
        if cache_path is None:
            cache_path = '/home/ubuntu/mytardis/var/tararchive_cache/'
        self.base_location = cache_path
        self.cache_path = abspathu(self.base_location)
        if base_url is None:
            base_url = settings.MEDIA_URL
        self.base_url = base_url
        self.dataset_id = dataset_id
        self.tar_path = tar_path
        self.tar_file = self.tar_path + '/' + self.dataset_id + '.tar'
        self.cache_file = self.cache_path + '/' + self.dataset_id + '.tar'

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

        # if newer_archive(self.tar_file, self.cache_file):
        #     print "archive newer or cache copy doesn't exist error"
        #     raise IOError("%s tape archive is newer than disk copy, please retrieve"
        #                   % self.dataset_id)

        # open tar in cache for reading
        tar = tarfile.open(self.cache_file)

        # filename = 'A dataset-1/Photo 4-10-12 2 15 00 PM.png'
        # filename = 'A dataset-1/SekZx.jpg'

        filename = name

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
        raise NotImplementedError()

    def exists(self, name):
        return os.path.exists(self.path(name))

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

def get_storage_class(import_path=None):
    return import_by_path(import_path or settings.DEFAULT_FILE_STORAGE)

class DefaultStorage(LazyObject):
    def _setup(self):
        self._wrapped = get_storage_class()()

default_storage = DefaultStorage()
