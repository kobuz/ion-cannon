"""Models."""

import time
import json

import pymongo
from bson.objectid import ObjectId
from bson.errors import InvalidId
from gridfs.errors import NoFile as GridNoFile

from . import get_storage
from .error import NotFound, NoFile


class Bullet(object):

    """Mapper for object in database."""

    __collection__ = 'Bullet'

    @classmethod
    def _get_collection(cls):
        return get_storage()['db'][cls.__collection__]

    @classmethod
    def _get_filesystem(cls):
        return get_storage()['fs']

    def __init__(self, **kwargs):
        # Fields.
        self.id = kwargs.get('_id')
        if self.id:
            self.id = str(self.id)
        self.headers = kwargs.get('headers')
        if self.headers and not isinstance(self.headers, dict):
            self.headers = json.loads(self.headers)
            if not isinstance(self.headers, dict):
                self.headers = {}
        self.uri = kwargs.get('uri')
        self.method = kwargs.get('method')
        self.content = kwargs.get('content')
        self.time = kwargs.get('time')
        self.file = kwargs.get('file')

    def save(self):
        """Save model to database."""
        collection = self._get_collection()
        fs = self._get_filesystem()
        obj = {
            'headers': json.dumps(self.headers),
            'uri': self.uri,
            'method': self.method,
            'time': self.time,
        }
        if self.content:
            file_obj = fs.put(self.content)
            obj['file'] = str(file_obj)
        result = collection.insert(obj)
        self.id = str(result)

    def has_file(self):
        """Check if model has any file.

        :return: Boolean.

        """
        fs = self._get_filesystem()
        return self.file is not None and fs.exists(ObjectId(self.file))

    def get_file(self):
        """Get file.

        :return: ``GridOut`` which is file-like object.

        """
        fs = self._get_filesystem()
        try:
            return fs.get(ObjectId(self.file))
        except GridNoFile:
            raise NoFile('Object with id "{}" has no file.'.format(self.id))

    def delete(self):
        """Delete model."""
        col = self._get_collection()
        fs = self._get_filesystem()
        col.remove({'_id': ObjectId(self.id)})
        if self.file:
            fs.delete(ObjectId(self.file))

    @classmethod
    def count(cls):
        """Count all available objects.

        :return: Amount of objects in database.
        :rtype: int

        """
        return cls._get_collection().count()

    @classmethod
    def all(cls):
        """Get all models."""
        for item in cls._get_collection().find():
            yield cls(**item)

    @classmethod
    def remove_all(cls):
        """Remove all objects from database."""
        for bullet in cls.all():
            bullet.delete()

    @classmethod
    def get_by_id(cls, identity):
        """Find model by its id.

        :param identity: Identity of model.
        :raises: ``NotFound`` when ``identity`` is not correct.
        :return: Initialized object.
        :rtype: ``Bullet``.

        """
        col = cls._get_collection()

        try:
            identity = ObjectId(identity)
        except InvalidId:
            raise NotFound(
                'Model with id "{}" was not found.'.format(identity))

        result = col.find_one({'_id': identity})
        if result:
            return cls(**result)
        else:
            raise NotFound(
                'Model with id "{}" was not found.'.format(identity))

    @classmethod
    def get_all_chronologically(cls):
        """Get all available models ordered ascending by time."""
        for item in cls._get_collection().find().sort(
                'time', pymongo.ASCENDING):
            yield cls(**item)

    @classmethod
    def get_latest(cls):
        """Get latest model from database, raise exception otherwise.

        :raises: ``NotFound`` if there are no objects in database.
        :return: Initialized object.
        :rtype: ``Bullet``.

        """
        for item in cls._get_collection().find().limit(1).sort(
                'time', pymongo.DESCENDING):
            return cls(**item)
        raise NotFound('No models in database.')


class MilisecondsClock(object):

    """Clock for fetch relative timestamps in miliseconds."""

    @staticmethod
    def _get_timestamp():
        return int(round(time.time() * 1000))

    def __init__(self, offset=0):
        self._zero = self._get_timestamp() - offset

    def check(self):
        """Check time (in miliseconds).

        :return: Time in miliseconds.
        :rtype: int

        """
        return self._get_timestamp() - self._zero


class Clock(object):

    """Singleton to keep reference to actually used Clock."""

    @classmethod
    def initialize(cls, clock):
        """Initialize clock.

        :param Clock clock: Concrete clock.

        """
        cls._clock = clock

    @classmethod
    def check(cls):
        """Check time.

        :return: Timestamp in miliseconds.

        """
        if not hasattr(cls, '_clock') or cls._clock is None:
            cls.initialize(MilisecondsClock())
        return cls._clock.check()

    @classmethod
    def cleanup(cls):
        """Destroy assigned clock."""
        cls._clock = None
