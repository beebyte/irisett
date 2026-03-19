# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Irisett is an async, API-driven monitoring server written in Python 3. It runs Nagios plugins to perform service checks and sends alerts on state changes. It is not a metric collection system.

## Commands

**Run tests** (requires a MySQL database — see `tests/sqlsetup.py` for credentials):
```bash
cd tests && pytest test_basic.py
```

**Run a single test:**
```bash
cd tests && pytest test_basic.py::test_metadata_basic
```

**Install dependencies:**
```bash
pip install -r requirements-dev.txt
```

**Start the server:**
```bash
python scripts/irisett -c examples/irisett.cfg
```

## Architecture

The codebase is organized around these top-level modules inside `irisett/`:

- **`main.py`** — Entry point. Reads config, wires up all subsystems, starts the asyncio event loop.
- **`monitor/active.py`** — `ActiveMonitorManager`: core scheduler that loads monitors from the DB, runs Nagios plugin commands concurrently (up to `max-concurrent-jobs`), tracks UP/DOWN state, and fires alerts on state transitions.
- **`monitor/active_sql.py`** — All SQL queries for monitors and monitor definitions (CRUD + results storage).
- **`notify/manager.py`** — `NotificationManager`: dispatches alerts to email, SMS (ClickSend), Slack webhooks, and HTTP callbacks using Jinja2 templates from config.
- **`sql/`** — Database abstraction: `db_mysql.py` (primary) and `db_sqlite.py` (alternative). Both expose the same `DBConnection` interface.
- **`webapi/`** — JSON REST API (default port 10000, HTTP Basic Auth). All programmatic management goes through here.
- **`webmgmt/`** — Optional aiohttp-jinja2 web dashboard (default port 11000). Loaded only if `[WEBMGMT]` section exists in config.
- **`object_models.py`** — Named tuple definitions for the core domain objects (monitors, defs, contacts, groups).
- **`contact.py`**, **`monitor_group.py`**, **`metadata.py`** — Domain logic for contacts, monitor groups, and key-value metadata attached to any object.

### Key Concepts

- **Monitor Definitions** (`active_monitor_defs`): templates that define a monitor type — `cmdline_filename` is the Nagios plugin binary, `cmdline_args_tmpl` is a Jinja2 template expanded with per-monitor args to produce the actual command line.
- **Monitors** (`active_monitors`): instances of a definition with specific arguments, state, and contacts.
- **State machine**: each monitor tracks consecutive failures; a monitor goes DOWN only after `down_threshold` consecutive failures. Alerts fire on UP→DOWN and DOWN→UP transitions.
- **Result retention**: if `result-retention` is set (hours), check results are stored in `active_monitor_results` and pruned on a schedule.
- **Metadata**: arbitrary key-value pairs on any object type/id, used for external system integration (e.g. `meta_organisation` in notification templates).
