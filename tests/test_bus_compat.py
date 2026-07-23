"""Tests for the ovos-bus-client compatibility shim in ovos_busmon.service.

Published ovos-bus-client releases only ship the threaded/sync
``MessageBusClient`` — ``AsyncMessageBusClient`` only exists in unmerged
ovos-bus-client PR #200. These tests cover both branches of ``_make_bus``:
using the async client when available, and falling back to
``_ThreadedBusClientAdapter`` (bridged onto the event loop) when it is not.
"""
from __future__ import annotations

import asyncio
import sys
import types
from unittest.mock import MagicMock

import pytest


def _reload_service():
    """Reload ovos_busmon.service so it re-evaluates the AsyncMessageBusClient
    import guard against whatever is currently in sys.modules."""
    sys.modules.pop("ovos_busmon.service", None)
    import ovos_busmon.service as service
    return service


def test_prefers_async_client_when_available():
    """When ovos_bus_client.client.AsyncMessageBusClient exists, _make_bus
    must use it (so nothing changes once bus-client PR #200 ships)."""
    import ovos_bus_client.client as obc_client

    class _FakeAsyncBus:
        def __init__(self, **kw):
            self.kw = kw

    original = getattr(obc_client, "AsyncMessageBusClient", None)
    obc_client.AsyncMessageBusClient = _FakeAsyncBus
    try:
        service = _reload_service()
        assert service._HAS_ASYNC_BUS_CLIENT is True
        bus = service._make_bus("localhost", 1234)
        assert isinstance(bus, _FakeAsyncBus)
    finally:
        if original is None:
            delattr(obc_client, "AsyncMessageBusClient")
        else:
            obc_client.AsyncMessageBusClient = original
        _reload_service()


@pytest.mark.asyncio
async def test_falls_back_to_threaded_adapter_without_async_client():
    """When AsyncMessageBusClient is absent (every released ovos-bus-client
    today), _make_bus must fall back to the threaded adapter instead of
    raising ImportError at import time."""
    import ovos_bus_client.client as obc_client

    had_attr = hasattr(obc_client, "AsyncMessageBusClient")
    original = getattr(obc_client, "AsyncMessageBusClient", None)
    if had_attr:
        delattr(obc_client, "AsyncMessageBusClient")
    try:
        service = _reload_service()
        assert service._HAS_ASYNC_BUS_CLIENT is False

        fake_sync_bus = MagicMock()
        fake_sync_bus.connected_event.wait.return_value = True
        with_patched = types.SimpleNamespace(MessageBusClient=lambda **kw: fake_sync_bus)
        original_msg_client = obc_client.MessageBusClient
        obc_client.MessageBusClient = with_patched.MessageBusClient
        try:
            bus = service._make_bus("localhost", 1234)
            assert isinstance(bus, service._ThreadedBusClientAdapter)
        finally:
            obc_client.MessageBusClient = original_msg_client
    finally:
        if had_attr:
            obc_client.AsyncMessageBusClient = original
        _reload_service()


@pytest.mark.asyncio
async def test_threaded_adapter_bridges_callbacks_and_lifecycle():
    """The adapter must expose connect/close/on/remove/emit and deliver
    callbacks registered via on() back onto the running event loop."""
    import ovos_busmon.service as service

    fake_sync_bus = MagicMock()
    fake_sync_bus.connected_event.wait.return_value = True

    adapter = service._ThreadedBusClientAdapter.__new__(service._ThreadedBusClientAdapter)
    adapter._bus = fake_sync_bus
    adapter._loop = asyncio.get_event_loop()
    adapter._bridged = {}

    received = []

    def _cb(raw):
        received.append(raw)

    adapter.on("message", _cb)
    fake_sync_bus.on.assert_called_once()
    registered_event, bridged_fn = fake_sync_bus.on.call_args[0]
    assert registered_event == "message"

    # Simulate the sync client's background thread firing the callback.
    bridged_fn("raw-payload")
    await asyncio.sleep(0)  # let call_soon_threadsafe run
    assert received == ["raw-payload"]

    adapter.remove("message", _cb)
    fake_sync_bus.remove.assert_called_once_with("message", bridged_fn)

    await adapter.connect()
    fake_sync_bus.run_in_thread.assert_called_once()

    await adapter.emit("some-message")
    fake_sync_bus.emit.assert_called_once_with("some-message")

    await adapter.close()
    fake_sync_bus.close.assert_called_once()
