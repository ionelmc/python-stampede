
Changelog
=========


1.1.0 (2015-10-19)
------------------

* Use more robust collection of child exit codes. Turns out that if there's enough pressure of the signalfd is fills up and
  needs extra ``os.waitpid()`` calls to collect the orphans.

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
