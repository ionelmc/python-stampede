import fcntl
from logging import getLogger

logger = getLogger(__name__)


class AlreadyLocked(Exception):
    pass


class FileLock(object):
    def __init__(self, path):
        self.lock_path = '%s.lock' % path
        self.fp = None

    def acquire(self):
        logger.debug('Attempting lock on %r', self.lock_path)
        try:
            self.fp = open(self.lock_path, 'wb')
            fcntl.lockf(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            logger.debug('Already locked!', self.lock_path)
            return False
        else:
            logger.debug('Locked %r', self.lock_path)
            return True

    def __enter__(self):
        if not self.acquire():
            raise AlreadyLocked()
        return self

    def release(self, _type=None, _value=None, _traceback=None):
        if self.fp is None:
            raise RuntimeError('Must be previously locked!')
        fcntl.lockf(self.fp, fcntl.LOCK_UN)

    __exit__ = release
