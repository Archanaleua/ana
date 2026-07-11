"""
MCP client.

Uses one persistent background event loop (so we're not paying the cost of
spinning up/tearing down a whole asyncio loop on every single call, and to
avoid Windows-specific event loop teardown issues).

IMPORTANT: each call still opens its own connection + session and closes it
before returning, ALL within a single coroutine (i.e. a single asyncio task).
The MCP streaming transport uses anyio task groups internally, which require
that whatever task opens a connection is the same task that closes it. An
earlier version of this file tried to keep one connection open and reuse it
across many separate calls (each scheduled as its own task via
run_coroutine_threadsafe) — that violates this rule and crashes with:
    RuntimeError: Attempted to exit cancel scope in a different task
                  than it was entered in
Do not "optimize" this into a long-lived shared session without solving that
problem first.
"""
import asyncio
import threading
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_SERVER_URL = "http://localhost:8000/mcp"

_loop = None
_thread = None
_loop_ready = threading.Event()


def _start_background_loop():
    """Run a persistent asyncio event loop in a background thread."""
    global _loop, _thread

    def _run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop_ready.set()
        _loop.run_forever()

    _thread = threading.Thread(target=_run, daemon=True)
    _thread.start()
    _loop_ready.wait(timeout=5)


def _ensure_loop():
    if _loop is None:
        _start_background_loop()


def _run_coro(coro, timeout: int = 20):
    """Run a coroutine on the background loop from sync code, with a timeout."""
    _ensure_loop()
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)


async def _list_tools_async():
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result.tools


async def _call_tool_async(tool_name: str, arguments: dict):
    async with streamablehttp_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result.content


def get_mcp_tools():
    """Sync wrapper — returns the list of tools your MCP server exposes."""
    return _run_coro(_list_tools_async())


def call_mcp_tool(tool_name: str, arguments: dict):
    """Sync wrapper — actually runs a tool on the MCP server and returns its result."""
    return _run_coro(_call_tool_async(tool_name, arguments))