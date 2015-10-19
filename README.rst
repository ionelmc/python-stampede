========
Stampede
========

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs|
    * - tests
      - | |travis| |requires|
        | |coveralls| |codecov|
        | |landscape| |scrutinizer| |codacy| |codeclimate|
    * - package
      - |version| |downloads| |wheel| |supported-versions| |supported-implementations|

.. |docs| image:: https://readthedocs.org/projects/python-stampede/badge/?style=flat
    :target: https://readthedocs.org/projects/python-stampede
    :alt: Documentation Status

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

.. |codacy| image:: https://img.shields.io/codacy/REPLACE_WITH_PROJECT_ID.svg?style=flat
    :target: https://www.codacy.com/app/ionelmc/python-stampede
    :alt: Codacy Code Quality Status

.. |codeclimate| image:: https://codeclimate.com/github/ionelmc/python-stampede/badges/gpa.svg
   :target: https://codeclimate.com/github/ionelmc/python-stampede
   :alt: CodeClimate Quality Status
.. |version| image:: https://img.shields.io/pypi/v/stampede.svg?style=flat
    :alt: PyPI Package latest release
    :target: https://pypi.python.org/pypi/stampede

.. |downloads| image:: https://img.shields.io/pypi/dm/stampede.svg?style=flat
    :alt: PyPI Package monthly downloads
    :target: https://pypi.python.org/pypi/stampede

.. |wheel| image:: https://img.shields.io/pypi/wheel/stampede.svg?style=flat
    :alt: PyPI Wheel
    :target: https://pypi.python.org/pypi/stampede

.. |supported-versions| image:: https://img.shields.io/pypi/pyversions/stampede.svg?style=flat
    :alt: Supported versions
    :target: https://pypi.python.org/pypi/stampede

.. |supported-implementations| image:: https://img.shields.io/pypi/implementation/stampede.svg?style=flat
    :alt: Supported implementations
    :target: https://pypi.python.org/pypi/stampede

.. |scrutinizer| image:: https://img.shields.io/scrutinizer/g/ionelmc/python-stampede/master.svg?style=flat
    :alt: Scrutinizer Status
    :target: https://scrutinizer-ci.com/g/ionelmc/python-stampede/

Event-loop based, miniature job queue and worker that runs the task in a subprocess (via fork). When multiple requests are made for the same
task they are collapsed into a single instance.

* Free software: BSD license

Installation
============

::

    pip install stampede

Documentation
=============

https://python-stampede.readthedocs.org/

Development
===========

To run the all tests run::

    tox
