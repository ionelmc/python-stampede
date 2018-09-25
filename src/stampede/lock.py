import fcntl
import os
from logging import getLogger

logger = getLogger(__name__)


class AlreadyLocked(Exception):
    pass


class FileLock(object):
    def __init__(self, path):
        self.lock_path = '%s.lock' % path
        self.fd = None

    def acquire(self):

        try:
            fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT | os.O_TRUNC)
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            logger.debug('FileLock(%s).acquire() => False (already locked)', self.lock_path)
            os.close(fd)
            return False
        else:
            logger.debug('FileLock(%s).acquire() => True', self.lock_path)
            self.fd = fd
            return True

    def __enter__(self):
        if not self.acquire():
            raise AlreadyLocked()
        return self

    def release(self, _type=None, _value=None, _traceback=None):
        if self.fd is None:
            raise RuntimeError('Must be previously locked!')
        fcntl.lockf(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)
        self.fd = None

    __exit__ = release
