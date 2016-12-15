What's what in irisett
======================

This document gives a brief overview of a number of concepts used in irisett.


(Active) Monitors
-----------------

Monitors are irisett service checks. They can be either UP or DOWN depending
on the results of recent service checks. A monitor will send alert
notifications to contacts attached to the monitor when it changes state.

What exactly will be monitored depends on monitor definition (see below)
that the monitor is based on, and the monitor arguments given to the
monitor.

A monitor can have zero or more arguments, the required arguments for a monitor
are defined by the monitor definition. Common arguments for a monitor are
for example the hostname/IP that should be monitored.

The default ping monitor takes three arguments:

 * Hostname/IP to monitor
 * Maximum permitted RTT
 * Maximum permitted packetloss

Some arguments may be optional. The only required above is the hostname/IP.

Monitors are standalone and not attached to any type of device/server as is
common in certain other monitoring systems. This is a deliberate design choice
and has its set of pros and cons, however for many types of monitors it
doesn't make sense to attach them to a particular device.


Monitor definitions
-------------------

Monitor definitions are as the name implies definitions / specifications of
different types of monitors. The monitor definitions in the default database
setup are:

 * Ping monitor
 * HTTP monitor
 * HTTPS certificate monitor

New monitor definitions can be created using the irisett API and command line
client.

Here's what the ping monitor looks like in the database:

```
Monitor defs:
               id: 1
             name: Ping monitor
      description: Monitor an IP using ICMP echo request packets.
           active: 1
 cmdline_filename: /usr/lib/nagios/plugins/check_ping
cmdline_args_tmpl: -H {{hostname}} -w {{rtt}},{{pl}}% -c {{rtt}},{{pl}}%
 description_tmpl: Ping monitor for {{hostname}}


Monitor def arguments:
*************************** 1. row ***************************
                   id: 1
active_monitor_def_id: 1
                 name: hostname
         display_name: IP address
          description: IP to monitor
             required: 1
        default_value: 
*************************** 2. row ***************************
                   id: 2
active_monitor_def_id: 1
                 name: rtt
         display_name: Max round trip time
          description: The maximum permitted round trip time in miliseconds
             required: 0
        default_value: 500
*************************** 3. row ***************************
                   id: 3
active_monitor_def_id: 1
                 name: pl
         display_name: Max packet loss
          description: The maximum permitted packet loss in percent
             required: 0
        default_value: 50
```

### cmdline_filename
The path to the nagios plugin to use for this monitor.

### cmdline_args_tmpl
A template used to create the arguments that will be passed to
cmdline_filename. Templates are
[Jinja2 templates](http://jinja.pocoo.org/docs/dev/templates/) and have
quite a bit of flexibility.

Two sets of arguments are passed to the template when expanding it.

The monitor definition argument default values, ie. rtt: 500, pl: 50, and
the monitors arguments, ie: hostname: 192.168.1.1

That would expand the monitor definitions cmdline_args_tmpl to:
  -H 192.168.1.1 -w 500,50% -c 500,50%

Any arguments supplied to the monitor override the default values
supplied in the monitor definition.


Contacts
--------

Contacts are sets of contact email/phone values that will be notified
when a monitor changes state. They are connected to monitors.


Object metadata
---------------

irisett is a single user, single organisation system. However, as it is
intended for integration with external systems, the external systems may
need to group monitors into different categories, or for other reasons
attach metadata to objects in irisett. This can be done using the irisett
metadata system.

```
mysql> select * from object_metadata;
+--------------------+-----------+--------------+-------+
| object_type        | object_id | key          | value |
+--------------------+-----------+--------------+-------+
| active_monitor     |         1 | organisation | 1     |
| active_monitor     |         1 | device       | 11    |
| contact            |         1 | organisation | 1     |
+--------------------+-----------+--------------+-------+
```

Arbitrary key value pairs can be attached to any device in irisett.
The metadata can then be used to query for specific monitors, contacts etc.
For example, if an external system wants to group all monitors for an
organisation, an organisation key value pair can be added to all monitors
for that organisation.

When fetching monitors, it is then possible to use the organisation metadata
to select which monitors to fetch.


Object binary data
------------------

Object binary data is similar to object metadata, except it is used for
binary blob storage attached to other objects. Object binary data can
not be used when querying for other objects.

