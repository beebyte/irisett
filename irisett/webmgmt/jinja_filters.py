from typing import Union
import datetime


def timestamp(ts: Union[int, float], include_ymd: bool = True) -> str:
    if not ts:
        return ""
    dt = datetime.datetime.fromtimestamp(ts)
    if include_ymd:
        ret = "%04d-%02d-%02d %02d:%02d:%02d" % (
            dt.year,
            dt.month,
            dt.day,
            dt.hour,
            dt.minute,
            dt.second,
        )
    else:
        ret = "%02d:%02d:%02d" % (dt.hour, dt.minute, dt.second)
    return ret
