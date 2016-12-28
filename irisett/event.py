"""A simple event tracing framework.

This is used to track events that are happing in irisett. For example
monitors call event.running(...) when they start/stop monitoring etc.

Other parts of irisett can then listen for events that are happening.
For example, the webmgmt ui can send events that are occuring over a websocket
to clients that want to watch events as they occur.
"""

from typing import Callable, Dict, Any
import time
import asyncio

from irisett import (
    stats,
    log,
)


class EventTracer:
    def __init__(self):
        self.listeners = {}
        stats.set('num_listeners', 0, 'EVENT')
        stats.set('events_fired', 0, 'EVENT')
        self.loop = asyncio.get_event_loop()

    def listen(self, callback: Callable) -> Dict[str, Any]:
        """Set a callback function that will receive events."""
        stats.inc('num_listeners', 'EVENT')
        listener = {
            'callback': callback,
            'created': time.time(),
        }
        self.listeners[id(listener)] = listener
        return listener

    def stop_listening(self, listener: Callable):
        """Remove a callback from the listener list."""
        if id(listener) in self.listeners:
            stats.dec('num_listeners', 'EVENT')
            del self.listeners[id(listener)]

    def running(self, event_name: str, **kwargs):
        """An event is running.

        Listener callbacks will be called with:
        callback(listener-dict, event-name, timestamp, arg-dict)
        """
        stats.inc('events_fired', 'EVENT')
        if not self.listeners:
            return
        timestamp = time.time()
        for listener in self.listeners.values():
            try:
                t = listener['callback'](listener, event_name, timestamp, kwargs)
                self.loop.create_task(t)
            except Exception as e:
                log.msg('Failed to run event listener callback: %s' % str(e))


default_tracer = EventTracer()
listen = default_tracer.listen
stop_listening = default_tracer.stop_listening
running = default_tracer.running
