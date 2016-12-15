Irisett: An API driven monitoring server
========================================

What is irisett?
----------------

Irisett is a small monitoring server that is aimed at easy integration with
other systems. A HTTP API is provided that is used to create monitors,
monitor definitions, query monitoring status etc.

Irisett is the core monitoring engine that schedules monitors, tracks monitor
status, sends alert notificiations etc. To perform service checks irisett
uses the vast array of Nagios plugins that are available.

Irisett is _not_ a metric collection system. It is intended for active
service monitoring, ie. ping checks, http checks etc.

Irisett currently does _not_ provide a web interface. Its primary use is for
integration with other systems and we haven't gotten around to building a
separate web interface just for irisett.


Features
--------

* API driven configuration
* API defined monitors
* API defined monitor defintions
* API defined contacts
* Active monitoring using the vast array of nagios plugins available
* Alerting notifications using email, sms, http callbacks and Slack integration


What motivated irisett?
-----------------------

Irisett came about as a result of a perceived lack of standalone (non-SaaS)
monitoring systems that could be easily managed using an API. Nagios for
example is a great monitoring system, but there is no easy way to manage
it remotely and integrate it with external systems.


Technology & requirements
-------------------------

Irisett is written in Python and makes heavy use of Pythons asyncio framework,
including the async/await keywords introduced in Python 3.5. Static typing is
also used extensively as per
[PEP 484](https://www.python.org/dev/peps/pep-0484/) and checked using
[mypy](http://mypy-lang.org/).

This means that Python 3.5 or above is required to run irisett along with
a number of extra packages from [pypi](https://pypi.python.org/pypi).


Installation
------------

The short version:

Make sure you have python >= 3.5. This includes for example Ubuntu 16.04
and above.

    $ python3 -m pip install -U irisett

Create a mysql database named irisett and grant privileges to an irisett
user. From the mysql command line client:

    $ GRANT ALL ON irisett.* TO 'irisett'@'localhost';

Copy the same [irisett.conf](https://github.com/beebyte/irisett/blob/master/examples/irisett.conf) to a suitable location and edit it to updates password
etc.

Make sure you have a local SMTP server running for alert notifications.

Install nagios monitoring plugins, on Ubuntu:

    $ sudo apt-get install monitoring-plugins

The default database setup assumes that the monitoring plugins are located
in /usr/lib/nagios/plugins

Launch irisett:

    $ irisett -c /path/to/irisett.conf

Use the command line client irisett-cli to communicate with the irisett
server.

The irisett default database setup includes three basic monitor types,
a ping monitor, a HTTP monitor and a HTTP SSL certificate expiration monitor.
Looking at the database can be a useful way to get a feel for how irisett
operates.

See the docs directory for further reading on installation and management
of irisett.


More documentation
------------------

See the [docs](https://github.com/beebyte/irisett/blob/master/docs/) directory
for more documentation

* [concepts.md](https://github.com/beebyte/irisett/blob/master/docs/concepts.md) - describes the concepts, object types and terminology used in irisett.
* [examples.md](https://github.com/beebyte/irisett/blob/master/docs/examples.md) - shows sample usage of the irisett command line client for getting things done in irisett.


Development status
------------------

Irisett is a work in progress and still in the early days of development. That
said it is used in production and should be relatively stable.


License
-------
Irisett is licensed under the terms of the MIT license (see the file LICENSE).
