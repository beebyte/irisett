"""A simple event tracing framework.

This is used to track events that are happing in irisett. For example
monitors call event.running(...) when they start/stop monitoring etc.

Other parts of irisett can then listen for events that are happening.
For example, the webmgmt ui can send events that are occuring over a websocket
to clients that want to watch events as they occur.

Performance concerns:
    The event tracing infrastructure is probably not great from a performance
    standpoint. However if there are no listeners connected the overhead
    is marginal.
"""

from typing import Callable, Dict, Optional, List, Set, Union, Any
import time
import asyncio

from irisett import (
    stats,
    log,
)


class EventListener:
    """A single listener for the event tracer.

    When EventTracer.listen is called an EventListener is created and
    returned. The EventListener keeps track of state for the a callback
    that wants to listen for events. filters etc. are kept in the
    EventListener object.
    """
    def __init__(self, tracer: 'EventTracer', callback: Callable, *,
                 event_filter: Optional[List[str]] = None,
                 active_monitor_filter: Optional[List[Union[str, int]]] = None) -> None:
        self.tracer = tracer
        self.callback = callback
        self.created = time.time()
        self.event_filter = self._parse_filter_list(event_filter)
        self.active_monitor_filter = self._parse_filter_list(active_monitor_filter)

    def set_event_filter(self, filter):
        self.event_filter = self._parse_filter_list(filter)

    def set_active_monitor_filter(self, filter):
        self.active_monitor_filter = self._parse_filter_list(self._parse_active_monitor_filter(filter))

    @staticmethod
    def _parse_active_monitor_filter(filter: Optional[List]) -> Any:
        if filter:
            filter = [int(n) for n in filter]
        return filter

    @staticmethod
    def _parse_filter_list(filter: Optional[List]) -> Any:
        """Parse a filter argument.

        If a list of filter arguments are passed in convert it to a set
        for increased lookup speed and reduced size.
        """
        ret = None
        if filter:
            ret = set(filter)
        return ret

    def wants_event(self, event_name: str, args: Dict):
        """Check if an event matches a listeners filters.

        If it does not, the listener will not receive the event.
        """
        ret = True
        if self.event_filter and event_name not in self.event_filter:
            ret = False
        elif self.active_monitor_filter and 'monitor' in args and args['monitor'].monitor_type() == 'active' \
                and args['monitor'].id not in self.active_monitor_filter:
            ret = False
        return ret


class EventTracer:
    """The main event tracer class.

    Creates listeners and receives events. When an event is received it
    is sent to all listeners (that matches the events filters.
    """
    def __init__(self):
        self.listeners = set()  # type: Set[EventListener]
        stats.set('num_listeners', 0, 'EVENT')
        stats.set('events_fired', 0, 'EVENT')
        self.loop = asyncio.get_event_loop()

    def listen(self, callback: Callable, *,
               event_filter: Optional[List[str]] = None,
               active_monitor_filter: Optional[List[Union[str, int]]] = None) -> EventListener:
        """Set a callback function that will receive events.

        Two filters can be used when selecting which events the callback will
        receive. event_filter can be a list of event names that must match.
        active_monitor_filter can be a list of active monitor ids that must match.
        """
        stats.inc('num_listeners', 'EVENT')
        listener = EventListener(self, callback, event_filter=event_filter, active_monitor_filter=active_monitor_filter)
        self.listeners.add(listener)
        return listener

    def stop_listening(self, listener: EventListener):
        """Remove a callback from the listener list."""
        if listener in self.listeners:
            stats.dec('num_listeners', 'EVENT')
            self.listeners.remove(listener)

    def running(self, event_name: str, **kwargs):
        """An event is running.

        Listener callbacks will be called with:
        callback(listener-dict, event-name, timestamp, arg-dict)
        """
        stats.inc('events_fired', 'EVENT')
        if not self.listeners:
            return
        timestamp = time.time()
        for listener in self.listeners:
            if not listener.wants_event(event_name, kwargs):
                continue
            try:
                t = listener.callback(listener, event_name, timestamp, kwargs)
                self.loop.create_task(t)
            except Exception as e:
                log.msg('Failed to run event listener callback: %s' % str(e))


default_tracer = EventTracer()
listen = default_tracer.listen
stop_listening = default_tracer.stop_listening
running = default_tracer.running
