
Changelog
=========

2.0.0 (2018-12-17)
------------------

* Use more robust collection of child exit codes. Turns out that if there's enough pressure of the signalfd is fills up and
  needs extra ``os.waitpid()`` calls to collect the orphans.
* Add a request API (``stampede.request``).
* Add a request API that also spawns the daemon if not running (``stampede.request_and_spawn``).
* Changed ``do_work`` to ``handle_task`` in StampedeWorker. **BACKWARDS INCOMPATIBLE**
* Update test grid to include Python 3.7 and PyPy3.
* Changed how results are passed to the client (JSON instead of some crappy custom text format).

1.0.0 (2015-10-19)
------------------

* Switch to `signalfd <https://pypi.python.org/pypi/signalfd>`_
  (from the unmaintained `python-signalfd <https://pypi.python.org/pypi/python-signalfd>`_).
* Switch to pytest.

0.0.1 (2013-10-30)
------------------

* ?

0.0.1 (2013-10-28)
------------------

* First release on PyPI.
