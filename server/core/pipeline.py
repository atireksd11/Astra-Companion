from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Callable

from core.turn import Turn

StepFn = Callable[[Turn], None]


class Pipeline:
    def __init__(self, steps: list[StepFn], step_timeout_s: float = 120.0) -> None:
        self.steps = steps
        self.step_timeout_s = step_timeout_s

    def run(self, turn: Turn) -> None:
        for step in self.steps:
            name = getattr(step, "__name__", step.__class__.__name__)
            t0 = time.perf_counter()
            pool = ThreadPoolExecutor(max_workers=1)
            fut = pool.submit(step, turn)
            try:
                fut.result(timeout=self.step_timeout_s)
            except FuturesTimeout:
                turn.error = "timeout"
                turn.notes["timeout_step"] = name
                fut.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                turn.timings_ms[name] = (time.perf_counter() - t0) * 1000.0
                break
            except Exception as exc:
                turn.error = "internal"
                turn.notes["step_exception"] = f"{name}: {exc}"
                pool.shutdown(wait=True, cancel_futures=False)
                turn.timings_ms[name] = (time.perf_counter() - t0) * 1000.0
                break
            else:
                pool.shutdown(wait=True, cancel_futures=False)
            turn.timings_ms[name] = (time.perf_counter() - t0) * 1000.0
            if turn.error:
                break
