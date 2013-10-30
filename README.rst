========================
    python-stampede
========================

.. image:: https://secure.travis-ci.org/ionelmc/python-stampede.png?branch=master
    :alt: Build Status
    :target: http://travis-ci.org/ionelmc/python-stampede

.. image:: https://coveralls.io/repos/ionelmc/python-stampede/badge.png?branch=master
    :alt: Coverage Status
    :target: https://coveralls.io/r/ionelmc/python-stampede

.. image:: https://pypip.in/d/python-stampede/badge.png
    :alt: PYPI Package
    :target: https://pypi.python.org/pypi/python-stampede

.. image:: https://pypip.in/v/python-stampede/badge.png
    :alt: PYPI Package
    :target: https://pypi.python.org/pypi/python-stampede

Event-loop based, miniature job queue and worker that runs the task in a subprocess (via fork). When multiple requests
are made for the same task they are collapsed into a single instance.

:Note: It doesn't support arguments to tasks. Not yet ...

Usage
=====

::

    class MacLeod(StampedeWorker):
        socket_name = 'test.sock'

        def do_work(self, task_name):
            import time
            time.sleep(18)

    man = MacLeod()
    man.run()

To create tasks::

    echo mytask > nc -U test.sock

Features
========

* TODO

Implementation
==============

TODO

TODO
====

* ???

Requirements
============

:OS: Linux
:Runtime: Python 2.6, 2.7, 3.2, 3.3 or PyPy
:Packages: python-signalfd


.. image:: https://d2weczhvl823v0.cloudfront.net/ionelmc/python-stampede/trend.png
   :alt: Bitdeli badge
   :target: https://bitdeli.com/free
