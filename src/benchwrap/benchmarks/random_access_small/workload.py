#!/usr/bin/env python3
"""Short irregular-memory benchmark inspired by HPCC RandomAccess."""

from __future__ import annotations

import os
import time

import numpy as np


def main() -> None:
    size = int(os.getenv("RANDOM_ACCESS_SIZE", "8388608"))
    updates = int(os.getenv("RANDOM_ACCESS_UPDATES", "25000000"))
    chunk = int(os.getenv("RANDOM_ACCESS_CHUNK", "1000000"))
    target_seconds = float(os.getenv("RANDOM_ACCESS_SECONDS", "30"))
    rng = np.random.default_rng(8675309)
    table = np.arange(size, dtype=np.uint64)
    done = 0
    checksum = np.uint64(0)

    print(
        f"random_access_small size={size} updates={updates} chunk={chunk} target_seconds={target_seconds}",
        flush=True,
    )
    start = time.time()
    rounds = 0
    while time.time() - start < target_seconds:
        done = 0
        while done < updates:
            count = min(chunk, updates - done)
            indices = rng.integers(0, size, size=count, dtype=np.int64)
            values = rng.integers(0, np.iinfo(np.uint64).max, size=count, dtype=np.uint64)
            np.bitwise_xor.at(table, indices, values)
            checksum ^= np.bitwise_xor.reduce(table[indices[: min(1024, count)]])
            done += count
        rounds += 1

    elapsed = time.time() - start
    final = int(checksum ^ np.bitwise_xor.reduce(table[:: max(1, size // 4096)]))
    print(
        f"random_access_small checksum={final} rounds={rounds} elapsed={elapsed:.3f}s "
        f"updates_per_s={(updates * rounds) / max(elapsed, 1e-9):.2f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
