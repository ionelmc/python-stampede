import logging
import os
import sys
import time

from stampede import StampedeWorker

try:
    from pytest_cov.embed import cleanup
    os._exit = lambda code, original=os._exit: cleanup() or original(code)
except ImportError:
    pass


PATH = '/tmp/stampede-tests'


class MockedStampedeWorker(StampedeWorker):
    alarm_time = 1

    def do_work(self, workspace_name):
        test_name = sys.argv[1]
        if test_name == 'test_simple':
            logging.critical('JOB %s EXECUTED', workspace_name.decode('ascii'))
        elif test_name == 'test_fail':
            raise Exception('FAIL')
        elif test_name == 'test_queue_collapse':
            assert workspace_name == b'test_queue_collapse'
            time.sleep(0.35)
            logging.critical('test_queue_collapse OK')
        elif test_name == 'test_timeout':
            logging.critical('test_timeout STARTED')
            time.sleep(2)
            logging.critical('test_timeout FAIL')
        elif test_name == 'test_bad_client':
            logging.critical('JOB %s EXECUTED', workspace_name)
            time.sleep(0.1)
        else:
            raise RuntimeError('Invalid test spec %r.' % test_name)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='[pid=%(process)d - %(asctime)s]: %(name)s - %(levelname)s - %(message)s',
    )

    daemon = MockedStampedeWorker(PATH)
    daemon.run()
    logging.info("DONE.")
