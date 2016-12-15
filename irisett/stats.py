"""Very basic statistics collection.

Basic functions for global statistics collection from various modules.
A global statistics dict is used that is accesses using functions
in this module.
"""

from typing import Dict, Optional
from collections import defaultdict

statistics = defaultdict(dict)  # type: defaultdict


def get_section(section: Optional[str]) -> Dict[str, float]:
    """Get a section (dict) from the global stats dict."""
    global statistics
    ret = statistics
    if section:
        ret = statistics[section]
    return ret


def set(var: str, value: float, section: Optional[str] = None):
    """Set a value."""
    stats = get_section(section)
    stats[var] = value


def inc(var: str, section: Optional[str] = None):
    """Increment a value."""
    stats = get_section(section)
    stats[var] += 1


def dec(var: str, section: Optional[str] = None):
    """Decrement a value"""
    stats = get_section(section)
    stats[var] -= 1


def get_stats() -> Dict[str, float]:
    """Get a dict of all saved statistics."""
    global statistics
    ret = {}  # type: Dict[str, float]
    for k, v in statistics.items():
        ret[k] = v
    return ret
