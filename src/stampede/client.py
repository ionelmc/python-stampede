import json
import os
import socket
from collections import namedtuple
from contextlib import closing
from logging import getLogger
from os.path import exists
from time import sleep
from time import time

from subprocess32 import DEVNULL
from subprocess32 import Popen

from .lock import FileLock
from .utils import IS_PY2

logger = getLogger(__name__)


class TaskFailed(Exception):
    def __init__(self, exit_code, pid):
        self.exit_code = exit_code
        self.pid = pid

    def __str__(self):
        return "Task failed with exit_code: %s (pid: %s)" % (self.exit_code, self.pid)


TaskSuccess = namedtuple("TaskSuccess", ["exit_code", "pid"])


def request(path, key, wait=True):
    logger.info("request %r wait=%s", key, wait)
    if not isinstance(key, bytes):
        raise TypeError("key should be bytes, not %s!" % type(key).__name__)
    if b"\n" in key or b"\r" in key:
        raise ValueError("key must not have line endings!")
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        with closing(sock):
            sock.settimeout(None)
            sock.connect("%s.sock" % path)
            if IS_PY2:
                fh = sock.makefile(bufsize=0)
            else:
                fh = sock.makefile("rwb", buffering=0)
            fh.write(b"%s\n" % key)
            if not wait:
                return
            line = fh.readline()
            logger.debug("request key=%r - got response %s", key, line)
            result = json.loads(line.decode('ascii'))
            if result["exit_code"]:
                raise TaskFailed(**result)
            else:
                return TaskSuccess(**result)
    except Exception:
        logger.exception("request key=%r wait=%s - FAILED:", key, wait)
        raise


def request_and_spawn(cli, path, key, wait=True, timeout=1):
    socket_path = "%s.sock" % path
    if exists(socket_path):
        logger.info("request_and_spawn key=%r wait=%s - socket already exists", key, wait)
        lock = FileLock(path)
        if lock.acquire():
            logger.info("request_and_spawn key=%r - got lock, spawning daemon ...", key)
            lock.release()
            os.unlink(socket_path)
            Popen(cli, stdin=DEVNULL, close_fds=True)
    else:
        logger.info("request_and_spawn key=%r wait=%s - no socket, spawning daemon ...", key, wait)
        Popen(cli, stdin=DEVNULL, close_fds=True)

    t = time()
    while not exists(socket_path) and time() - t < timeout:
        sleep(0.01)

    return request(path, key, wait=wait)
