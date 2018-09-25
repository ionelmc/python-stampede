========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| |requires|
        | |coveralls| |codecov|
        | |landscape| |scrutinizer| |codacy| |codeclimate|
    * - package
      - | |version| |wheel| |supported-versions| |supported-implementations|
        | |commits-since|



.. |travis| image:: https://travis-ci.org/ionelmc/python-stampede.svg?branch=master
    :alt: Travis-CI Build Status
    :target: https://travis-ci.org/ionelmc/python-stampede

.. |requires| image:: https://requires.io/github/ionelmc/python-stampede/requirements.svg?branch=master
    :alt: Requirements Status
    :target: https://requires.io/github/ionelmc/python-stampede/requirements/?branch=master

.. |coveralls| image:: https://coveralls.io/repos/ionelmc/python-stampede/badge.svg?branch=master&service=github
    :alt: Coverage Status
    :target: https://coveralls.io/r/ionelmc/python-stampede

.. |codecov| image:: https://codecov.io/github/ionelmc/python-stampede/coverage.svg?branch=master
    :alt: Coverage Status
    :target: https://codecov.io/github/ionelmc/python-stampede

.. |landscape| image:: https://landscape.io/github/ionelmc/python-stampede/master/landscape.svg?style=flat
    :target: https://landscape.io/github/ionelmc/python-stampede/master
    :alt: Code Quality Status

.. |codacy| image:: https://img.shields.io/codacy/REPLACE_WITH_PROJECT_ID.svg
    :target: https://www.codacy.com/app/ionelmc/python-stampede
    :alt: Codacy Code Quality Status

.. |codeclimate| image:: https://codeclimate.com/github/ionelmc/python-stampede/badges/gpa.svg
   :target: https://codeclimate.com/github/ionelmc/python-stampede
   :alt: CodeClimate Quality Status

.. |version| image:: https://img.shields.io/pypi/v/stampede.svg
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/stampede

.. |commits-since| image:: https://img.shields.io/github/commits-since/ionelmc/python-stampede/v1.0.0.svg
    :alt: Commits since latest release
    :target: https://github.com/ionelmc/python-stampede/compare/v1.0.0...master

.. |wheel| image:: https://img.shields.io/pypi/wheel/stampede.svg
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/stampede

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/stampede.svg
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/stampede

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/stampede.svg
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/stampede

.. |scrutinizer| image:: https://img.shields.io/scrutinizer/g/ionelmc/python-stampede/master.svg
    :alt: Scrutinizer Status
    :target: https://scrutinizer-ci.com/g/ionelmc/python-stampede/


.. end-badges

A really simple job queue. Uses a rudimentary event loop and runs tasks in subprocesses (managed with signalfd).
Doesn't support task arguments. Task results are rudimentary (only succcess or failure with exit code). When multiple
requests are made for the same task they are collapsed into a single request.

* Free software: BSD 2-Clause License

Installation
============

::

    pip install stampede

Documentation
=============


To use the project:

.. code-block:: python

    import stampede


    class MyWorker(StampedeWorker):

        def do_work(self, name):
            print("Perfoming work for task:", name)


Development
===========

To run the all tests run::

    tox
