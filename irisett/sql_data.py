"""Define tables and initial testing data for irisett.

These tables are automatically created if they are missing when
irisett starts up.
"""

# noinspection PyPep8
SQL_TABLES = [
    """
        CREATE TABLE `version` (
            `version` varchar(100) NOT NULL,
            PRIMARY KEY (`version`)
        )
        """,
    """
        create table active_monitors
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            `def_id` INT NOT NULL,
            `state` varchar(10) NOT NULL,
            `state_ts` INT NOT NULL,
            `msg` VARCHAR(200) NOT NULL,
            `alert_id` INT NULL,
            `deleted` boolean NOT NULL DEFAULT false,
            `checks_enabled` boolean NOT NULL DEFAULT true,
            `alerts_enabled` boolean NOT NULL DEFAULT true,
            PRIMARY KEY (`id`)
        )
        """,
    """
        create table active_monitor_args
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            monitor_id INT NOT NULL,
            name varchar(20),
            value varchar(100),
            PRIMARY KEY (`id`),
            KEY `monitor_id_idx` (`monitor_id`)
        )
        """,
    """
        create table active_monitor_alerts
        (
            `id` int not null auto_increment,
            `monitor_id` int not null,
            `start_ts` int not null,
            `end_ts` int not null,
            `alert_msg` varchar(200) not null,
            primary key (`id`),
            key `monitor_id_idx` (`monitor_id`)
        )
        """,
    """
        create table active_monitor_defs
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            name varchar(50),
            description varchar(100),
            active boolean,
            cmdline_filename varchar(50),
            cmdline_args_tmpl varchar(200),
            description_tmpl varchar(100),
            PRIMARY KEY (`id`)
        )
        """,
    """
        create table active_monitor_def_args
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            active_monitor_def_id INT NOT NULL,
            name varchar(20),
            display_name varchar(30),
            description varchar(100),
            required boolean,
            default_value varchar(50),
            PRIMARY KEY (`id`),
            KEY `monitor_def_id_idx` (`active_monitor_def_id`)
        )
        """,
    """
        create table active_monitor_contacts
        (
            active_monitor_id INT NOT NULL,
            contact_id INT NOT NULL,
            PRIMARY KEY (`active_monitor_id`, `contact_id`),
            KEY `monitor_id_idx` (`active_monitor_id`)
        )
        """,
    """
        create table active_monitor_contact_groups
        (
            active_monitor_id INT NOT NULL,
            contact_group_id INT NOT NULL,
            PRIMARY KEY (`active_monitor_id`, `contact_group_id`),
            KEY `monitor_id_idx` (`active_monitor_id`)
        )
        """,
    """
        create table contacts
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            name varchar(100) NULL,
            email varchar(100) NULL,
            phone varchar(100) NULL,
            active boolean,
            PRIMARY KEY (`id`)
        )
        """,
    """
        create table contact_groups
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            name varchar(100),
            active boolean,
            PRIMARY KEY (`id`)
        )
        """,
    """
        create table contact_group_contacts
        (
            contact_group_id INT NOT NULL,
            contact_id INT NOT NULL,
            PRIMARY KEY (`contact_group_id`, `contact_id`),
            KEY `contact_group_id_idx` (`contact_group_id`)
        )
        """,
    """
        create table object_metadata
        (
            `object_type` varchar(30),
            `object_id` int not null,
            `key` varchar(30) not null,
            `value` varchar(100) not null,
            PRIMARY KEY (`object_type`, `object_id`, `key`),
            KEY `type_id_idx` (`object_type`, `object_id`),
            KEY `key_value_idx` (`key`, `value`)
        )
        """,
    """
        create table object_bindata
        (
            `object_type` varchar(30),
            `object_id` int not null,
            `key` varchar(30) not null,
            `value` blob not null,
            PRIMARY KEY (`object_type`, `object_id`, `key`),
            KEY `type_id_idx` (`object_type`, `object_id`)
        )
        """,
    """
        create table monitor_groups
        (
            `id` INT NOT NULL AUTO_INCREMENT,
            `name` varchar(100),
            PRIMARY KEY (`id`)
        )
        """,
    """
        create table monitor_group_active_monitors
        (
            monitor_group_id INT NOT NULL,
            active_monitor_id INT NOT NULL,
            PRIMARY KEY (`monitor_group_id`, `active_monitor_id`),
            KEY `monitor_group_id_idx` (`monitor_group_id`)
        )
        """,
    """
        create table monitor_group_contacts
        (
            monitor_group_id INT NOT NULL,
            contact_id INT NOT NULL,
            PRIMARY KEY (`monitor_group_id`, `contact_id`),
            KEY `monitor_group_id_idx` (`monitor_group_id`)
        )
        """,
    """
        create table monitor_group_contact_groups
        (
            monitor_group_id INT NOT NULL,
            contact_group_id INT NOT NULL,
            PRIMARY KEY (`monitor_group_id`, `contact_group_id`),
            KEY `monitor_group_id_idx` (`monitor_group_id`)
        )
        """,
]
SQL_MONITOR_DEFS = [
    """insert into active_monitor_defs (name, description, active, cmdline_filename,
        cmdline_args_tmpl, description_tmpl)
        values (
            "Ping monitor",
            "Monitor an IP using ICMP echo request packets.",
            True,
            "/usr/lib/nagios/plugins/check_ping",
            "-H {{hostname}} -w {{rtt}},{{pl}}% -c {{rtt}},{{pl}}%",
            "Ping monitor for {{hostname}}"
            )
        """,
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (1, "hostname", "IP address", "IP to monitor", true, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (1, "rtt", "Max round trip time", "The maximum permitted round trip time in miliseconds", false, "500")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (1, "pl", "Max packet loss", "The maximum permitted packet loss in percent", false, "50")""",
    """insert into active_monitor_defs
        (name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl) values (
            "HTTP monitor",
            "Monitor a website.",
            True,
            "/usr/lib/nagios/plugins/check_http",
            '-I {{hostname}}{%if vhost%} -H {{vhost}}{%endif%} -f follow{%if match%} -s "{{match}}"{%endif%}{%if ssl%} -S{%endif%}{%if url%} -u {{url}}{%endif%}',
            'HTTP monitor for {%if vhost%}{{vhost}}{%else%}{{hostname}}{%endif%}'
            )
        """,
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "hostname", "Hostname of server/site", "The hostname of the site to monitor", true, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "vhost", "Virtual host", "The virtual host to monitor", false, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "match", "Match string", "Match a string in the returned site data", false, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "ssl", "Use HTTPS/SSL", "Use HTTP/SSL monitoring", false, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "url", "Url to monitor", "Monitor a specific URL", false, "/")""",
    """insert into active_monitor_defs
        (name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl) values (
            "HTTPS certificate monitor",
            "Monitor a websites SSL certificate.",
            True,
            "/usr/lib/nagios/plugins/check_http",
            "-I {{hostname}}{%if vhost%} -H {{vhost}}{%endif%} -C {{age}},{{age}}",
            'HTTP SSL cert monitor for {%if vhost%}{{vhost}}{%else%}{{hostname}}{%endif%}'
            )
        """,
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (3, "hostname", "Hostname of server/site", "The hostname of the site to monitor", true, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (3, "vhost", "Virtual host", "The virtual host to monitor", false, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (3, "age", "Certificate max age", "The max age (in days) of the site certificate", false, "14")""",
]
SQL_MONITORS = [
    """insert into active_monitors (def_id, state, state_ts, msg) values (1, 'UNKNOWN', 0, '')""",
    """insert into active_monitor_args (monitor_id, name, value) values (1, "hostname", "127.0.0.1")""",
]

SQL_ALL = SQL_TABLES + SQL_MONITOR_DEFS + SQL_MONITORS
