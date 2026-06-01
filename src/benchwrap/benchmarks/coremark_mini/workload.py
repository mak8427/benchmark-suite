#!/usr/bin/env python3
"""Small CoreMark-inspired CPU benchmark with deterministic validation."""

from __future__ import annotations

import os
import time
import zlib

import numpy as np


def _state_machine(values: np.ndarray) -> int:
    state = 0x345678
    for value in values:
        item = int(value)
        if item & 1:
            state = ((state << 5) ^ item ^ (state >> 2)) & 0xFFFFFFFF
        elif item % 3 == 0:
            state = ((state * 33) + item) & 0xFFFFFFFF
        else:
            state = (state ^ ((item << 7) | (item >> 3))) & 0xFFFFFFFF
    return state


def _crc(value: int, digest: int) -> int:
    return zlib.crc32(int(value).to_bytes(8, "little", signed=False), digest)


def main() -> None:
    size = int(os.getenv("COREMARK_MINI_SIZE", "120000"))
    iters = int(os.getenv("COREMARK_MINI_ITERS", "80"))
    target_seconds = float(os.getenv("COREMARK_MINI_SECONDS", "30"))
    rng = np.random.default_rng(0xC0DE)
    data = rng.integers(0, 1_000_000, size=size, dtype=np.uint64)
    matrix = rng.integers(0, 127, size=(64, 64), dtype=np.int64)
    vector = rng.integers(0, 127, size=64, dtype=np.int64)

    print(
        f"coremark_mini size={size} iters={iters} target_seconds={target_seconds}",
        flush=True,
    )
    start = time.time()
    digest = 0
    acc = 0
    rounds = 0
    while time.time() - start < target_seconds:
        for step in range(iters):
            data.sort()
            acc ^= _state_machine(data[:: max(1, size // 4096)])
            vector = (matrix @ vector + step + rounds) % 104729
            digest = _crc(acc ^ int(vector.sum()), digest)
            data = np.roll(data, (step % 97) + 1)
        rounds += 1

    elapsed = time.time() - start
    if digest == 0:
        raise RuntimeError("unexpected zero digest")
    operations = size * iters
    print(
        f"coremark_mini digest={digest} rounds={rounds} operations={operations * rounds} elapsed={elapsed:.3f}s "
        f"score={(operations * rounds) / max(elapsed, 1e-9):.2f} ops/s",
        flush=True,
    )


if __name__ == "__main__":
    main()
