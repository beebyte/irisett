"""Basic logging functionality.

Supports logging to stdout, syslog and file.
"""

from typing import Optional

import os
import os.path
import logging
import logging.handlers

from irisett import errors

# Yes yes, globals are ugly.
logger = None


def configure_logging(logtype: str, logfilename: Optional[str]=None, debug_logging: bool=False,
                      rotate_length: int=1000000, max_rotated_files: int=250):
    global logger
    level = logging.INFO
    if debug_logging:
        level = logging.DEBUG
    if logtype not in ['stdout', 'syslog', 'file']:
        raise errors.IrisettError('invalid logtype name %s' % logtype)
    if rotate_length is None:
        rotate_length = 1000000
    if max_rotated_files is None:
        max_rotated_files = 250
    logger = logging.getLogger('irisett')
    logger.setLevel(level)

    handler = None
    if logtype == 'stdout':
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    elif logtype == 'syslog':
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        handler.setLevel(level)
        formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    else:  # == file
        logpath = os.path.split(logfilename)[0]
        if not os.path.exists(logpath):
            os.makedirs(logpath)
        handler = logging.handlers.RotatingFileHandler(logfilename, maxBytes=rotate_length,
                                                       backupCount=max_rotated_files)
        handler.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def msg(logmsg: str, section=None):
    """Log a standard message."""
    global logger
    if not logger:
        return
    if section:
        logmsg = '[%s] %s' % (section, logmsg)
    logger.info(logmsg)


err = msg


def debug(logmsg: str, section=None):
    """Log a debug message."""
    global logger
    if not logger:
        return
    if section:
        logmsg = '[%s] %s' % (section, logmsg)
    logger.debug(logmsg)


class LoggingMixin:
    """class mixin for improved? logging output."""

    def log_msg(self, logmsg):
        msg('%s %s' % (str(self), logmsg))

    def log_debug(self, logmsg):
        debug('%s %s' % (str(self), logmsg))
