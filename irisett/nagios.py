"""Run nagios plugins and return something useful.

Runs nagios plugins as defined in:
    https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/3/en/pluginapi.html

The plugin binary is executed and the return code is evaluated to determine
a result for the check. The text output is separated from the performance
data output. Nothing more is currently done with the performance data.
"""

from typing import List, Tuple, Union, cast
import asyncio.subprocess

from irisett import log


class NagiosError(Exception):
    pass


class MonitorFailedError(NagiosError):
    pass


STATUS_OK = 0
STATUS_WARNING = 1
STATUS_CRITICAL = 2
STATUS_UNKNOWN = 3


# noinspection PyUnusedLocal
async def run_plugin(executable: str, args: List[str], timeout: int) -> Tuple[str, List[str]]:
    run_args = [executable] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *run_args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    except FileNotFoundError:
        raise NagiosError('executable not found')
    stdin_data, stderr_data = await proc.communicate()
    std_data = stdin_data + stderr_data
    await proc.wait()
    if proc.returncode not in [STATUS_OK, STATUS_WARNING, STATUS_CRITICAL]:
        raise MonitorFailedError(std_data)
    text, perf = parse_plugin_output(std_data)
    if proc.returncode not in [STATUS_OK, STATUS_WARNING]:
        raise MonitorFailedError(text)
    return text, perf


def parse_plugin_output(output: Union[str, bytes]) -> Tuple[str, List[str]]:
    """Parse nagios output.

    Splits the data into a text string and performance data.
    """
    output = decode_plugin_output(output)
    if '|' not in output:
        text = output
        perf = []  # type: List[str]
    else:
        text, _perf = output.split('|', 1)
        perf = _perf.split('|')
    text = text.strip()
    return text, perf


def decode_plugin_output(output: Union[str, bytes]) -> str:
    """Decode nagios output from latin-1."""
    try:
        if type(output) == bytes:
            output = cast(bytes, output)
            output = output.decode('latin-1', 'replace')
    except Exception as e:
        log.debug('nagios.encode_monitor_output: error: %s' % str(e))
        output = ''
    return cast(str, output)
