"""Define tables and initial testing data for irisett.

These tables are automatically created if they are missing when
irisett starts up.
"""

# The current active version of the database, increase when making changes
# and create upgrade queries in SQL_UPGRADES below.
CUR_VERSION = 2

SQL_VERSION = [
    """insert into version (version) values ('%s')""" % str(CUR_VERSION),
]

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
            `id` INTEGER PRIMARY KEY NOT NULL,
            `def_id` INT NOT NULL,
            `state` varchar(10) NOT NULL,
            `state_ts` INT NOT NULL,
            `msg` VARCHAR(200) NOT NULL,
            `alert_id` INT NULL,
            `deleted` boolean NOT NULL DEFAULT 0,
            `checks_enabled` boolean NOT NULL DEFAULT 1,
            `alerts_enabled` boolean NOT NULL DEFAULT 1
        )
        """,
    """
        create table active_monitor_args
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            monitor_id INT NOT NULL,
            name varchar(20),
            value varchar(100)
        )
        """,
    """
        CREATE INDEX active_monitor_args_monitor_id_idx ON active_monitor_args(monitor_id)
        """,
    """
        create table active_monitor_alerts
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `monitor_id` int not null,
            `start_ts` int not null,
            `end_ts` int not null,
            `alert_msg` varchar(200) not null
        )
        """,
    """
        create table active_monitor_results
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `monitor_id` int not null,
            `timestamp` int not null,
            `state` varchar(10) not null,
            `result_msg` varchar(200) not null,
        )
        """,
    """
        CREATE INDEX active_monitor_alerts_monitor_id_idx ON active_monitor_alerts(monitor_id)
        """,
    """
        create table active_monitor_defs
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            name varchar(50),
            description varchar(100),
            active boolean,
            cmdline_filename varchar(50),
            cmdline_args_tmpl varchar(1000),
            description_tmpl varchar(100)
        )
        """,
    """
        create table active_monitor_def_args
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            active_monitor_def_id INT NOT NULL,
            name varchar(20),
            display_name varchar(30),
            description varchar(100),
            required boolean,
            default_value varchar(50)
        )
        """,
    """
        CREATE INDEX monitor_def_id_idx ON active_monitor_def_args(active_monitor_def_id)
        """,
    """
        create table active_monitor_contacts
        (
            active_monitor_id INT NOT NULL,
            contact_id INT NOT NULL,
            PRIMARY KEY (`active_monitor_id`, `contact_id`)
        )
        """,
    """
        CREATE INDEX monitor_def_monitor_id_idx ON active_monitor_contacts(active_monitor_id)
        """,
    """
        create table active_monitor_contact_groups
        (
            active_monitor_id INT NOT NULL,
            contact_group_id INT NOT NULL,
            PRIMARY KEY (`active_monitor_id`, `contact_group_id`)
        )
        """,
    """
        CREATE INDEX monitor_id_idx ON active_monitor_contact_groups(active_monitor_id)
        """,
    """
        create table contacts
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            name varchar(100) NULL,
            email varchar(100) NULL,
            phone varchar(100) NULL,
            active boolean
        )
        """,
    """
        create table contact_groups
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            name varchar(100),
            active boolean
        )
        """,
    """
        create table contact_group_contacts
        (
            contact_group_id INT NOT NULL,
            contact_id INT NOT NULL,
            PRIMARY KEY (`contact_group_id`, `contact_id`)
        )
        """,
    """
        CREATE INDEX contact_group_id_idx ON contact_group_contacts(contact_group_id)
        """,
    """
        create table object_metadata
        (
            `object_type` varchar(30),
            `object_id` int not null,
            `key` varchar(30) not null,
            `value` varchar(100) not null,
            PRIMARY KEY (`object_type`, `object_id`, `key`)
        )
        """,
    """
        CREATE INDEX object_metadata_type_id_idx ON object_metadata(object_type, object_id)
        """,
    """
        CREATE INDEX key_value_idx ON object_metadata(key, value)
        """,
    """
        create table object_bindata
        (
            `object_type` varchar(30),
            `object_id` int not null,
            `key` varchar(30) not null,
            `value` blob not null,
            PRIMARY KEY (`object_type`, `object_id`, `key`)
        )
        """,
    """
        CREATE INDEX object_bindata_type_id_idx ON object_bindata(object_type, object_id)
        """,
    """
        create table monitor_groups
        (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `parent_id` INT NULL,
            `name` varchar(100)
        )
        """,
    """
        CREATE INDEX parent_idx ON monitor_groups(parent_id)
        """,
    """
        CREATE INDEX name_idx ON monitor_groups(name)
        """,
    """
        create table monitor_group_active_monitors
        (
            monitor_group_id INT NOT NULL,
            active_monitor_id INT NOT NULL,
            PRIMARY KEY (`monitor_group_id`, `active_monitor_id`)
        )
        """,
    """
        CREATE INDEX monitor_group_active_monitors_monitor_group_id_idx ON monitor_group_active_monitors(monitor_group_id)
        """,
    """
        CREATE INDEX active_monitor_id_idx ON monitor_group_active_monitors(active_monitor_id)
        """,
    """
        create table monitor_group_contacts
        (
            monitor_group_id INT NOT NULL,
            contact_id INT NOT NULL,
            PRIMARY KEY (`monitor_group_id`, `contact_id`)
        )
        """,
    """
        CREATE INDEX monitor_group_contacts_monitor_group_id_idx ON monitor_group_contacts(monitor_group_id)
        """,
    """
        create table monitor_group_contact_groups
        (
            monitor_group_id INT NOT NULL,
            contact_group_id INT NOT NULL,
            PRIMARY KEY (`monitor_group_id`, `contact_group_id`)
        )
        """,
    """
        CREATE INDEX monitor_group_contact_groups_monitor_group_id_idx ON monitor_group_contact_groups(monitor_group_id)
        """,
]
SQL_MONITOR_DEFS = [
    """insert into active_monitor_defs (name, description, active, cmdline_filename,
        cmdline_args_tmpl, description_tmpl)
        values (
            "Ping monitor",
            "Monitor an IP using ICMP echo request packets.",
            1,
            "/usr/lib/nagios/plugins/check_ping",
            "-H {{hostname}} -w {{rtt}},{{pl}}% -c {{rtt}},{{pl}}%",
            "Ping monitor for {{hostname}}"
            )
        """,
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (1, "hostname", "IP address", "IP to monitor", 1, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (1, "rtt", "Max round trip time", "The maximum permitted round trip time in miliseconds", 0, "500")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (1, "pl", "Max packet loss", "The maximum permitted packet loss in percent", 0, "50")""",
    """insert into active_monitor_defs
        (name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl) values (
            "HTTP monitor",
            "Monitor a website.",
            1,
            "/usr/lib/nagios/plugins/check_http",
            '-I {{hostname}}{%if vhost%} -H {{vhost}}{%endif%} -f follow{%if match%} -s "{{match}}"{%endif%}{%if ssl%} -S --sni{%endif%}{%if url%} -u {{url}}{%endif%}',
            'HTTP monitor for {%if vhost%}{{vhost}}{%else%}{{hostname}}{%endif%}'
            )
        """,
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "hostname", "Hostname of server/site", "The hostname of the site to monitor", 1, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "vhost", "Virtual host", "The virtual host to monitor", 0, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "match", "Match string", "Match a string in the returned site data", 0, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "ssl", "Use HTTPS/SSL", "Use HTTP/SSL monitoring", 0, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (2, "url", "Url to monitor", "Monitor a specific URL", 0, "/")""",
    """insert into active_monitor_defs
        (name, description, active, cmdline_filename, cmdline_args_tmpl, description_tmpl) values (
            "HTTPS certificate monitor",
            "Monitor a websites SSL certificate.",
            1,
            "/usr/lib/nagios/plugins/check_http",
            "-I {{hostname}}{%if vhost%} -H {{vhost}}{%endif%} -C {{age}},{{age}} --sni",
            'HTTP SSL cert monitor for {%if vhost%}{{vhost}}{%else%}{{hostname}}{%endif%}'
            )
        """,
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (3, "hostname", "Hostname of server/site", "The hostname of the site to monitor", 1, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (3, "vhost", "Virtual host", "The virtual host to monitor", 0, "")""",
    """insert into active_monitor_def_args
        (active_monitor_def_id, name, display_name, description, required, default_value)
        values (3, "age", "Certificate max age", "The max age (in days) of the site certificate", 0, "14")""",
]
SQL_MONITORS = [
    """insert into active_monitors (def_id, state, state_ts, msg) values (1, 'UNKNOWN', 0, '')""",
    """insert into active_monitor_args (monitor_id, name, value) values (1, "hostname", "127.0.0.1")""",
]


# The queries to run for an emptry database
SQL_BARE = SQL_TABLES + SQL_VERSION

# The queries to run when adding default monitors.
SQL_ALL = SQL_TABLES + SQL_VERSION + SQL_MONITOR_DEFS + SQL_MONITORS

# Queries to run when upgrade the database.
# Add a new section for each version, ie:
# { VERSION: [COMMANDS ...]
SQL_UPGRADES = {
    2: [
        """
            create table active_monitor_results
            (
                `id` INTEGER PRIMARY KEY NOT NULL,
                `monitor_id` int not null,
                `timestamp` int not null,
                `result_msg` varchar(200) not null,
            )
            """,
    ],
    3: [
        """ALTER TABLE `active_monitor_results` ADD `state` varchar(10) NOT NULL AFTER `timestamp`""",
    ],
}
