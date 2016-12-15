Irisett sample usage
====================

Irisett supplies a command line client that can be used to communicate
with the irisett server over the HTTP API.

The irisett-cli command provides basic documentation with the -h and <command> -h options.


Monitors
--------

```irisett-cli -p webapi-password add-active-monitor -d 1 -a hostname:127.0.0.1```


```
irisett-cli -p webapi-password get-active-monitors -i 1

[{'alert_id': None,
  'alerts_enabled': 1,
  'args': {'hostname': '127.0.0.1'},
  'checks_enabled': 1,
  'consecutive_checks': 0,
  'expanded_args': ['-H', '127.0.0.1', '-w', '500,50%', '-c', '500,50%'],
  'id': 1,
  'last_check': 1481755989.224422,
  'metadata': {},
  'monitor_def': {'arg_spec': [{'default_value': '',
                                'id': 1,
                                'name': 'hostname',
                                'required': 1},
                               {'default_value': '500',
                                'id': 2,
                                'name': 'rtt',
                                'required': 0},
                               {'default_value': '50',
                                'id': 3,
                                'name': 'pl',
                                'required': 0}],
                  'cmdline_args_tmpl': '-H {{hostname}} -w {{rtt}},{{pl}}% -c '
                                       '{{rtt}},{{pl}}%',
                  'cmdline_filename': '/usr/lib/nagios/plugins/check_ping',
                  'description_tmpl': 'Ping monitor for {{hostname}}',
                  'id': 1,
                  'name': 'Ping monitor'},
  'monitor_description': 'Ping monitor for 127.0.0.1',
  'monitoring': False,
  'msg': 'PING OK - Packet loss = 0%, RTA = 0.07 ms',
  'state': 'UP',
  'state_elapsed': '2 days, 11 hours',
  'state_ts': 1481540595}]
```


Monitor definitions
-------------------

```
irisett-cli -p webapi-password get-active-monitor-defs -i 1

[{'active': 1,
  'arg_def': [{'default_value': '',
               'description': 'IP to monitor',
               'display_name': 'IP address',
               'id': 1,
               'name': 'hostname',
               'required': 1},
              {'default_value': '500',
               'description': 'The maximum permitted round trip time in '
                              'miliseconds',
               'display_name': 'Max round trip time',
               'id': 2,
               'name': 'rtt',
               'required': 0},
              {'default_value': '50',
               'description': 'The maximum permitted packet loss in percent',
               'display_name': 'Max packet loss',
               'id': 3,
               'name': 'pl',
               'required': 0}],
  'cmdline_args_tmpl': '-H {{hostname}} -w {{rtt}},{{pl}}% -c {{rtt}},{{pl}}%',
  'cmdline_filename': '/usr/lib/nagios/plugins/check_ping',
  'description': 'Monitor an IP using ICMP echo request packets.',
  'description_tmpl': 'Ping monitor for {{hostname}}',
  'id': 1,
  'name': 'Ping monitor'}]
```
