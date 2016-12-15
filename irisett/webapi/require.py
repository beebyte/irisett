"""A set of functions used to validate HTTP input data.

These functions are primarily used to valid that arguments sent in http
requests are what they are supposed to be.
"""

from typing import Union, Any, Dict, List, cast, Optional, SupportsInt

from irisett.webapi.errors import InvalidData


def require_str(value: Any, convert: bool=False, allow_none: bool=False) -> Optional[str]:
    """Make sure a value is a str.

    Used when dealing with http input data.
    """
    if value is None and allow_none:
        return value
    if type(value) != str:
        if not convert:
            raise InvalidData('value  was %s(%s), expected str' % (type(value), value))
        value = str(value)
    return value


def require_bool(value: Optional[Union[bool, str, int]], convert=False, allow_none=False) -> Optional[bool]:
    """Make sure a value is a boolean.

    Used when dealing with http input data.
    """
    if value is None and allow_none:
        return value
    if type(value) != bool:
        if not convert:
            raise InvalidData()
        if value in [None, 0, '0', 'false', 'False']:
            value = False
        elif value in [1, '1', 'true', 'True']:
            value = True
        else:
            raise InvalidData('value was %s(%s), expected bool' % (type(value), value))
    return cast(bool, value)


def require_dict(value: Optional[Dict[Any, Any]], key_type: Any=None, value_type: Any=None,
                 allow_none: bool=False) -> Optional[Dict[str, str]]:
    """Make sure a value is a Dict[key_type, value_type].

    Used when dealing with http input data.
    """
    if value is None and allow_none:
        return value
    if type(value) != dict:
        raise InvalidData('value was %s(%s), expected dict' % (type(value), value))
    value = cast(Dict, value)
    if key_type or value_type:
        for k, v in value.items():
            if key_type and type(k) != key_type:
                raise InvalidData('dict key was %s(%s), expected %s' % (type(k), k, key_type))
            if value_type and type(v) != value_type:
                raise InvalidData('dict value was %s(%s), expected %s' % (type(v), v, key_type))
    return value


def require_list(value: Optional[List[Any]], item_type=None, allow_none=False) -> Optional[List[Any]]:
    """Make sure a value is a List[item_type].

    Used when dealing with http input data.
    """
    if value is None and allow_none:
        return value
    if type(value) != list:
        raise InvalidData('value was %s, expected list' % type(value))
    value = cast(List, value)
    if item_type:
        for item in value:
            if type(item) != item_type:
                raise InvalidData('list item was %s, expected %s' % (type(item), item_type))
    return value


def require_int(value: Optional[Union[SupportsInt, str, bytes]], allow_none=False) -> Optional[int]:
    """Make sure a value is an int.

    Used when dealing with http input data.
    """
    if value is None and allow_none:
        return value
    value = cast(Union[SupportsInt, str, bytes], value)
    try:
        value = int(value)
    except (ValueError, TypeError):
        raise InvalidData('value was %s(%s), expected list' % (type(value), value))
    return value
