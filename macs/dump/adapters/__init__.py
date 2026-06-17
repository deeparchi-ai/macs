"""Runtime adapters: map a specific agent runtime's events into the MACS core.

Each adapter normalizes its runtime's telemetry into ``(kind, data)`` events
(request | response | api_error | tool_pre | tool_post | subagent | approval)
and feeds the :class:`~macs.dump.collector.TurnCollector`. Hermes is adapter #1.
"""
