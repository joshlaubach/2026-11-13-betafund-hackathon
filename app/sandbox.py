"""Run SymPy work in a child process that is killed on timeout.

Thread-based timeouts cannot interrupt a hung SymPy call, so each job gets its
own interpreter. The job is sent as JSON on stdin and the result read from
stdout; see app/worker.py for the task registry.
"""
import asyncio
import json
import os
import sys
import time
import weakref
from dataclasses import dataclass
from typing import Any

from app.config import settings

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_limits: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _limit() -> asyncio.Semaphore:
    """One semaphore per event loop: a Semaphore binds to the first loop that contends for it."""
    loop = asyncio.get_running_loop()
    if loop not in _limits:
        _limits[loop] = asyncio.Semaphore(settings.sandbox_concurrency)
    return _limits[loop]


class SandboxTimeout(Exception):
    pass


class SandboxError(Exception):
    pass


@dataclass
class SandboxResult:
    value: Any
    elapsed_ms: int


async def run(task: str, args: dict, timeout: float | None = None) -> SandboxResult:
    timeout = timeout or settings.sandbox_timeout_s
    payload = json.dumps({"task": task, "args": args}).encode()
    async with _limit():
        t0 = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "app.worker",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=_ROOT,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(payload), timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise SandboxTimeout(f"{task} exceeded {timeout}s") from None
        elapsed = int((time.perf_counter() - t0) * 1000)
    try:
        msg = json.loads(out)
    except json.JSONDecodeError:
        raise SandboxError(f"worker crashed (exit {proc.returncode}): {err.decode()[-300:]}") from None
    if not msg["ok"]:
        raise SandboxError(msg["error"])
    return SandboxResult(msg["value"], elapsed)
