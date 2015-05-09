from os import path
from datetime import datetime

from django.conf import settings
from django.core.files import File
from django.core.urlresolvers import reverse
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from celery.contrib.methods import task

from tardis.tardis_portal.util import generate_file_checksums

from .fields import DirectoryField
from .dataset import Dataset
from .storage import StorageBox, StorageBoxOption, StorageBoxAttribute

import logging
logger = logging.getLogger(__name__)

IMAGE_FILTER = (Q(mimetype__startswith='image/') &
                ~Q(mimetype='image/x-icon')) |\
    (Q(datafileparameterset__datafileparameter__name__units__startswith="image"))  # noqa


#TODOsteve

class DataFile(models.Model):
    """Class to store meta-data about a file.  The physical copies of a
    file are described by distinct DataFileObject instances.

    :attribute dataset: the foreign key to the
       :class:`tardis.tardis_portal.models.Dataset` the file belongs to.
    :attribute filename: the name of the file, excluding the path.
    :attribute size: the size of the file.
    :attribute created_time: time the file was added to tardis
    :attribute modification_time: last modification time of the file
    :attribute mimetype: for example 'application/pdf'
    :attribute md5sum: digest of length 32, containing only hexadecimal digits
    :attribute sha512sum: digest of length 128, containing only hexadecimal
        digits
    """

    dataset = models.ForeignKey(Dataset)
    filename = models.CharField(max_length=400)
    directory = DirectoryField(blank=True, null=True)
    size = models.CharField(blank=True, max_length=400)
    created_time = models.DateTimeField(null=True, blank=True)
    modification_time = models.DateTimeField(null=True, blank=True)
    mimetype = models.CharField(blank=True, max_length=80)
    md5sum = models.CharField(blank=True, max_length=32)
    sha512sum = models.CharField(blank=True, max_length=128)
    deleted = models.BooleanField(default=False)
    deleted_time = models.DateTimeField(blank=True, null=True)
    version = models.IntegerField(default=1)

    @property
    def file_object(self):
        on_disk_files = self.file_objects.filter(
            ~Q(storage_box__attributes__value='on tape'))
        if len(on_disk_files) > 0:
            return on_disk_files[0].file_object
        all_dfos = self.file_objects.all()
        if len(all_dfos) > 0:
            return all_dfos[0].file_object
        return None

    @file_object.setter
    def file_object(self, file_object):
        '''
        replace contents of file in all its locations
        '''
        oldobjs = []
        if self.file_objects.count() > 0:
            oldobjs = list(self.file_objects.all())
        s_boxes = [obj.storage_box for obj in oldobjs]
        if len(s_boxes) == 0:
            s_boxes = [self.get_default_storage_box()]
        for box in s_boxes:
            newfile = DataFileObject(datafile=self,
                                     storage_box=box)
            newfile.save()
            newfile.file_object = file_object
            newfile.verify.delay()
        if len(oldobjs) > 0:
            for obj in oldobjs:
                obj.delete()

    def get_default_storage_box(self):
        '''
        try to guess appropriate box from files, dataset or experiment
        '''
        boxes_used = StorageBox.objects.filter(file_objects__datafile=self)
        if len(boxes_used) > 0:
            return boxes_used[0]
        dataset_boxes = self.dataset.get_all_storage_boxes_used()
        if len(dataset_boxes) > 0:
            return dataset_boxes[0]
        experiment_boxes = StorageBox.objects.filter(
            file_objects__datafile__dataset__experiments__in=self
            .dataset.experiments.all())
        if len(experiment_boxes) > 0:
            return experiment_boxes[0]
        # TODO: select one accessible to the owner of the file
        return StorageBox.get_default_storage()

    def get_receiving_storage_box(self):
        default_box = self.get_default_storage_box()
        child_boxes = [
            box for box in default_box.child_boxes.all()
            if box.attributes.filter(
                key="type", value="receiving").count() == 1]
        if len(child_boxes) > 0:
            return child_boxes[0]

        loc_boxes = StorageBoxOption.objects.filter(
            key='location',
            value=getattr(settings, 'DEFAULT_RECEIVING_DIR', '/tmp'))\
            .values_list('storage_box', flat=True)
        attr_boxes = StorageBoxAttribute.objects.filter(
            key="type", value="receiving")\
            .values_list('storage_box', flat=True)
        existing_default = set(loc_boxes) & set(attr_boxes)
        if len(existing_default) > 0:
            return StorageBox.objects.get(id=existing_default.pop())

        new_box = StorageBox.create_local_box(
            location=getattr(settings, 'DEFAULT_RECEIVING_DIR', '/tmp'))
        new_attr = StorageBoxAttribute(storage_box=new_box,
                                       key='type', value='receiving')
        new_box.attributes.add(new_attr)
        new_box.master_box = default_box
        new_box.save()
        return new_box

    class Meta:
        app_label = 'tardis_portal'
        ordering = ['filename']
        unique_together = ['dataset', 'directory', 'filename', 'version']

    @classmethod
    def sum_sizes(cls, datafiles):
        """
        Takes a query set of datafiles and returns their total size.
        """
        def sum_str(*args):
            def coerce_to_long(x):
                try:
                    return long(x)
                except ValueError:
                    return 0
            return sum(map(coerce_to_long, args))
        # Filter empty sizes, get array of sizes, then reduce
        return reduce(sum_str, datafiles.exclude(size='')
                                        .values_list('size', flat=True), 0)

    def save(self, *args, **kwargs):
        require_checksums = kwargs.pop('require_checksums', True)
        if settings.REQUIRE_DATAFILE_CHECKSUMS and \
                not self.md5sum and not self.sha512sum and require_checksums:
            raise Exception('Every Datafile requires a checksum')
        elif settings.REQUIRE_DATAFILE_SIZES and \
                not self.size:
            raise Exception('Every Datafile requires a file size')
        super(DataFile, self).save(*args, **kwargs)

    def get_size(self):
        return self.size

    def getParameterSets(self, schemaType=None):
        """Return datafile parametersets associated with this datafile.

        """
        from .parameters import Schema
        if schemaType == Schema.DATAFILE or schemaType is None:
            return self.datafileparameterset_set.filter(
                schema__type=Schema.DATAFILE)
        else:
            raise Schema.UnsupportedType

    def __unicode__(self):
        return "%s %s # %s" % (self.sha512sum[:32] or self.md5sum,
                               self.filename, self.mimetype)

    def get_mimetype(self):
        if self.mimetype:
            return self.mimetype
        else:
            suffix = path.splitext(self.filename)[-1]
            try:
                import mimetypes
                return mimetypes.types_map[suffix.lower()]
            except KeyError:
                return 'application/octet-stream'

    def get_view_url(self):
        import re
        viewable_mimetype_patterns = ('image/.*', 'text/.*')
        if not any(re.match(p, self.get_mimetype())
                   for p in viewable_mimetype_patterns):
            return None
        return reverse('view_datafile', kwargs={'datafile_id': self.id})

    def get_download_url(self):
        return '/api/v1/dataset_file/%d/download' % self.id

    def get_file(self):
        return self.file_object

    def get_absolute_filepath(self):
        dfos = self.file_objects.all()
        if len(dfos) > 0:
            return dfos[0].get_full_path()
        else:
            return None

    def get_file_getter(self):
        return self.file_objects.all()[0].get_file_getter()

    def is_local(self):
        return self.file_objects.all()[0].is_local()

    def has_image(self):
        from .parameters import DatafileParameter

        if self.is_image():
            return True

        # look for image data in parameters
        pss = self.getParameterSets()

        if not pss:
            return False

        for ps in pss:
            dps = DatafileParameter.objects.filter(
                parameterset=ps, name__data_type=5,
                name__units__startswith="image")

            if len(dps):
                return True

        return False

    def is_image(self):
        '''
        returns True if it's an image and not an x-icon and not an img
        the image/img mimetype is made up though and may need revisiting if
        there is an official img mimetype that does not refer to diffraction
        images
        '''
        mimetype = self.get_mimetype()
        return mimetype.startswith('image/') \
            and mimetype not in ('image/x-icon', 'image/img')

    def get_image_data(self):
        from .parameters import DatafileParameter

        if self.is_image():
            return self.get_file()

        # look for image data in parameters
        pss = self.getParameterSets()

        if not pss:
            return None

        for ps in pss:
            dps = DatafileParameter.objects.filter(
                parameterset=ps, name__data_type=5,
                name__units__startswith="image")

            if len(dps):
                preview_image_par = dps[0]

        if preview_image_par:
            file_path = path.abspath(path.join(settings.METADATA_STORE_PATH,
                                               preview_image_par.string_value))

            preview_image_file = file(file_path)

            return preview_image_file

        else:
            return None

    def is_public(self):
        from .experiment import Experiment
        return Experiment.objects.filter(
            datasets=self.dataset,
            public_access=Experiment.PUBLIC_ACCESS_FULL).exists()

    def _has_any_perm(self, user_obj):
        if not hasattr(self, 'id'):
            return False
        return self.dataset

    def _has_view_perm(self, user_obj):
        return self._has_any_perm(user_obj)

    def _has_change_perm(self, user_obj):
        return self._has_any_perm(user_obj)

    def _has_delete_perm(self, user_obj):
        return self._has_any_perm(user_obj)

    # @property
    # def default_dfo(self):
    #     s_box = self.get_default_storage_box()
    #     try:
    #         return self.file_objects.get(storage_box=s_box)
    #     except DataFileObject.DoesNotExist:
    #         return None

    @property
    def verified(self):
        return all([obj.verified for obj in self.file_objects.all()]) \
            and len(self.file_objects.all()) > 0

    def verify(self, reverify=False):
        return all([obj.verify() for obj in self.file_objects.all()
                    if reverify or not obj.verified])


class DataFileObject(models.Model):
    '''
    holds one copy of the data for a datafile
    '''

    datafile = models.ForeignKey(DataFile, related_name='file_objects')
    storage_box = models.ForeignKey(StorageBox, related_name='file_objects')
    uri = models.TextField(blank=True, null=True)  # optional
    created_time = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)
    last_verified_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        app_label = 'tardis_portal'
        unique_together = ['datafile', 'storage_box']

    def __unicode__(self):
        try:
            return 'Box: %(storage_box)s, URI: %(uri)s, verified: %(v)s' % {
                'storage_box': str(self.storage_box),
                'uri': self.uri,
                'v': str(self.verified)
            }
        except:
            return 'undefined'

    def _get_identifier(self):
        '''
        the default identifier would be directory and file name, but it may
        not work for all backends. This function aims to abstract it.
        '''

        def default_identifier(dfo):
            if dfo.uri is None:
                path_parts = ["%s-%s" % (dfo.datafile.dataset.description
                                         or 'untitled',
                                         dfo.datafile.dataset.id)]
                if dfo.datafile.directory is not None:
                    path_parts += [dfo.datafile.directory]
                path_parts += [dfo.datafile.filename.strip()]
                dfo.uri = path.join(*path_parts)
                dfo.save()
            return dfo.uri

        build_identifier = getattr(self._storage, 'build_identifier',
                                   lambda x: None)
        return build_identifier(self) or default_identifier(self)

    def get_save_location(self):
        return self.storage_box.get_save_location(self)

    @property
    def file_object(self):
        '''
        a set of accessor functions that convert the file information to a
        standard python file object for reading and copy the contents of an
        existing file_object into the storage backend.
        '''
        cached_file_object = getattr(self, '_cached_file_object', None)
        if cached_file_object is None or cached_file_object.closed:
            cached_file_object = self._storage.open(self._get_identifier())
            self._cached_file_object = cached_file_object
        return self._cached_file_object

    @file_object.setter
    def file_object(self, file_object):
        '''
        write contents of file object to storage_box
        '''
        if file_object.closed:
            file_object = File(file_object)
            file_object.open()
        file_object.seek(0)
        self.uri = self._storage.save(self._get_identifier(), file_object)
        self.save()

    @property
    def _storage(self):
        cached_storage = getattr(self, '_cached_storage', None)
        if cached_storage is None:
            cached_storage = self.storage_box\
                                 .get_initialised_storage_instance()
            self._cached_storage = cached_storage
        return self._cached_storage

    @task(name='tardis_portal.dfo.copy_file', ignore_result=True)
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
            logger.error(
                'file move failed for dfo id: %s, with error: %s' %
                (self.id, str(e)))
            return False
        if verify:
            copy.verify.delay()
        return copy

    @task(name='tardis_portal.dfo.move_file', ignore_result=True)
    def move_file(self, dest_box=None):
        '''
        moves a file
        copies first, then synchronously verifies
        deletes file if copy is true copy and has been verified
        '''
        copy = self.copy_file(dest_box=dest_box, verify=False)
        if copy and copy.id != self.id and (copy.verified or copy.verify()):
            self.delete()
        return copy

    @task(name="tardis_portal.verify_dfo_method", ignore_result=True)  # noqa # too complex
    def verify(self):  # too complex # noqa
        self.checksums = generate_file_checksums
        md5, sha512, size, mimetype_buffer = self.checksums(
            self.file_object)
        df_md5 = self.datafile.md5sum
        df_sha512 = self.datafile.sha512sum
        if df_sha512 is None or df_sha512 == '':
            if md5 != df_md5:
                logger.error('DataFileObject with id %d did not verify. '
                             'MD5 sums did not match')
                return False
            self.datafile.sha512sum = sha512
            self.datafile.save()
        elif df_md5 is None or df_md5 == '':
            if sha512 != df_sha512:
                logger.error('DataFileObject with id %d did not verify. '
                             'SHA512 sums did not match')
                return False
            self.datafile.md5sum = md5
            self.datafile.save()
        else:
            if not (md5 == df_md5 and sha512 == df_sha512):
                logger.error('DataFileObject with id %d did not verify. '
                             'Checksums did not match')
                return False
        df_size = self.datafile.size
        if df_size is None or df_size == '':
            self.datafile.size = size
            self.datafile.save()
        elif int(df_size) != size:
            logger.error('DataFileObject with id %d did not verify. '
                         'File size did not match')
            return False

        self.verified = True
        self.last_verified_time = datetime.now()
        self.save(update_fields=['verified', 'last_verified_time'])
        return True

    def get_full_path(self):
        return self._storage.path(self.uri)


@receiver(pre_delete, sender=DataFileObject, dispatch_uid='dfo_delete')
def delete_dfo(sender, instance, **kwargs):
    if instance.datafile.file_objects.count() > 1:
        try:
            instance._storage.delete(instance.uri)
        except NotImplementedError:
            logger.info('deletion not supported on storage box %s, '
                        'for dfo id %s' % (str(instance.storage_box),
                                           str(instance.id)))
    else:
        logger.debug('Did not delete file dfo.id '
                     '%s, because it was the last copy' % instance.id)
