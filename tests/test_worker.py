import json
import os
import pwd
import socket
import sys
import time
from contextlib import closing
from contextlib import contextmanager

import pytest
from process_tests import TestProcess
from process_tests import dump_on_error
from process_tests import wait_for_strings

import helper

UDS_PATH = '%s.sock' % helper.PATH
TIMEOUT = int(os.getenv('TEST_TIMEOUT', 5))
PY3 = sys.version_info[0] == 3


@contextmanager
def connection(timeout=1):
    with closing(socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)) as sock:
        sock.settimeout(timeout)
        sock.connect(UDS_PATH)
        if PY3:
            fh = sock.makefile("rwb", buffering=0)
        else:
            fh = sock.makefile(bufsize=0)
        with closing(fh):
            yield fh


def test_simple():
    with TestProcess(sys.executable, helper.__file__, 'simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection() as fh:
                fh.write(b"first")
                fh.write(b"-second\n")
                line = fh.readline()
                assert b'"exit_code": 0' in line
                wait_for_strings(proc.read, TIMEOUT,
                                 '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                 'JOB first-second EXECUTED',
                                 'completed. Passing back results to',
                                 'Queues => 0 workspaces')


def test_fail():
    with TestProcess(sys.executable, helper.__file__, 'fail') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection() as fh:
                fh.write(b"first")
                fh.write(b"-second\n")
                line = fh.readline()
                assert b'"exit_code": 255' in line
                wait_for_strings(proc.read, TIMEOUT,
                                 '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                 'Failed task',
                                 'Exception: FAIL',
                                 'Queues => 0 workspaces')


def test_incomplete_request():
    with TestProcess(sys.executable, helper.__file__, 'simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection(2) as fh:
                fh.write(b"first")
                line = fh.readline()
                assert line == b''
                wait_for_strings(proc.read, TIMEOUT,
                                 'Failed to read request from client %s:%s' % (
                                     pwd.getpwuid(os.getuid())[0], os.getpid()))


def test_queue_collapse():
    with TestProcess(sys.executable, helper.__file__, 'queue_collapse') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            clients = []
            for _ in range(5):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect(UDS_PATH)
                if PY3:
                    fh = sock.makefile("rwb", buffering=0)
                else:
                    fh = sock.makefile(bufsize=0)
                fh.write(b"queue_collapse\n")
                clients.append((fh, sock))
            try:
                t1 = time.time()
                for fh, _ in clients:
                    fh.readline()
                delta = time.time() - t1
                if delta > TIMEOUT:
                    raise AssertionError('Jobs took too much time (%0.2f sec)' % delta)
                wait_for_strings(proc.read, TIMEOUT,
                                 'queue_collapse OK',
                                 '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()))
            finally:
                [(fh.close(), sock.close()) for fh, sock in clients]


def test_timeout():
    with TestProcess(sys.executable, helper.__file__, 'timeout') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection(3) as fh:
                fh.write(b"foobar\n")
                line = fh.readline()
                json.loads(line.decode('ascii'))["exit_code"] == 14
                wait_for_strings(proc.read, TIMEOUT,
                                 '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                                 'timeout STARTED',
                                 'completed. Passing back results to')
                assert 'timeout FAIL' not in proc.read()


def test_custom_exit_code():
    with TestProcess(sys.executable, helper.__file__, 'custom_exit_code') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            with connection(3) as fh:
                fh.write(b"asdf\n")
                line = fh.readline()
                json.loads(line.decode('ascii'))["exit_code"] == 123


def test_bad_client():
    with TestProcess(sys.executable, helper.__file__, 'simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(UDS_PATH)
            if PY3:
                fh = sock.makefile("rwb", buffering=0)
            else:
                fh = sock.makefile(bufsize=0)

            fh.write(b"first-second\n")
            fh.close()
            sock.close()
            time.sleep(0.2)
            assert proc.is_alive
            wait_for_strings(proc.read, TIMEOUT,
                             '%s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()),
                             'JOB first-second EXECUTED',
                             'completed. Passing back results to',
                             'Failed to send response to ')


def test_empty_request():
    with TestProcess(sys.executable, helper.__file__, 'simple') as proc:
        with dump_on_error(proc.read):
            wait_for_strings(proc.read, TIMEOUT, 'Queues =>')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect(UDS_PATH)
            if PY3:
                fh = sock.makefile("rwb", buffering=0)
            else:
                fh = sock.makefile(bufsize=0)

            fh.write(b"\n")
            fh.close()
            sock.close()
            time.sleep(0.2)
            assert proc.is_alive
            wait_for_strings(proc.read, TIMEOUT,
                             'Got empty request from client %s:%s' % (pwd.getpwuid(os.getuid())[0], os.getpid()))


def test_double_instance():
    from stampede import StampedeWorker
    StampedeWorker._SingleInstanceMeta__inst = None
    StampedeWorker(helper.PATH)
    with pytest.raises(RuntimeError):
        StampedeWorker(helper.PATH)


def test_subclassing():
    from stampede import StampedeWorker

    class MyWorker(StampedeWorker):
        def __init__(self, path, config):
            super(MyWorker, self).__init__(path)
            self.config = config

    MyWorker._SingleInstanceMeta__inst = None
    worker = MyWorker(helper.PATH, 'foobar')
    assert worker.config == 'foobar'
