"""Random utility functions."""

from typing import Union, cast


def parse_bool(string: Union[str, bool]) -> bool:
    """Parse a string and return a boolean."""
    if type(string) == bool:
        return cast(bool, string)
    string = cast(str, string)
    ret = False
    if string.lower() == 'true':
        ret = True
    return ret


intervals = (
    ('weeks', 604800),  # 60 * 60 * 24 * 7
    ('days', 86400),  # 60 * 60 * 24
    ('hours', 3600),  # 60 * 60
    ('minutes', 60),
    ('seconds', 1),
)


def get_display_time(seconds: float, granularity: int = 2) -> str:
    """Get a string suitable for display for a number of seconds."""
    result = []

    # Avoid using floats, it makes the result ugly.
    seconds = int(seconds)
    for name, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value == 1:
                name = name.rstrip('s')
            result.append("{} {}".format(value, name))
    ret = ', '.join(result[:granularity])
    return ret
