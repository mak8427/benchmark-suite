#!/usr/bin/env python3
"""Small NAS IS-inspired integer ranking benchmark."""

from __future__ import annotations

import os
import time

import numpy as np


def main() -> None:
    keys = int(os.getenv("NPB_IS_KEYS", "2500000"))
    iters = int(os.getenv("NPB_IS_ITERS", "12"))
    max_key = int(os.getenv("NPB_IS_MAX_KEY", "1048576"))
    target_seconds = float(os.getenv("NPB_IS_SECONDS", "30"))
    rng = np.random.default_rng(271828)
    values = rng.integers(0, max_key, size=keys, dtype=np.int32)

    print(
        f"npb_is_small keys={keys} iters={iters} max_key={max_key} target_seconds={target_seconds}",
        flush=True,
    )
    start = time.time()
    checksum = 0
    probes = np.array([0, keys // 4, keys // 2, (3 * keys) // 4, keys - 1])
    rounds = 0
    while time.time() - start < target_seconds:
        for step in range(iters):
            index = (step + rounds) % keys
            values[index] = (values[index] + step + rounds + 1) % max_key
            hist = np.bincount(values, minlength=max_key)
            ranks = np.cumsum(hist, dtype=np.int64)
            sorted_values = np.sort(values)
            if not np.all(sorted_values[1:] >= sorted_values[:-1]):
                raise RuntimeError("sort validation failed")
            checksum ^= int(ranks[sorted_values[probes]].sum() + sorted_values[probes].sum())
        rounds += 1

    elapsed = time.time() - start
    print(
        f"npb_is_small checksum={checksum} rounds={rounds} keys_ranked={keys * iters * rounds} elapsed={elapsed:.3f}s "
        f"keys_per_s={(keys * iters * rounds) / max(elapsed, 1e-9):.2f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
