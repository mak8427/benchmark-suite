#!/usr/bin/env python3
"""Small NAS EP-inspired random-number throughput benchmark."""

from __future__ import annotations

import os
import time

import numpy as np


def main() -> None:
    pairs = int(os.getenv("NPB_EP_PAIRS", "8000000"))
    chunks = int(os.getenv("NPB_EP_CHUNKS", "16"))
    target_seconds = float(os.getenv("NPB_EP_SECONDS", "30"))
    chunk_pairs = max(1, pairs // chunks)
    rng = np.random.default_rng(314159265)
    bins = np.zeros(10, dtype=np.int64)
    sx = 0.0
    sy = 0.0

    print(
        f"npb_ep_small pairs={pairs} chunks={chunks} target_seconds={target_seconds}",
        flush=True,
    )
    start = time.time()
    rounds = 0
    while time.time() - start < target_seconds:
        for _ in range(chunks):
            x = rng.standard_normal(chunk_pairs)
            y = rng.standard_normal(chunk_pairs)
            r = x * x + y * y
            sx += float(x.sum())
            sy += float(y.sum())
            counts = np.bincount(np.minimum(r.astype(np.int64), 9), minlength=10)
            bins += counts[:10]
        rounds += 1

    elapsed = time.time() - start
    checksum = float(np.dot(bins, np.arange(10)) + sx + sy)
    if not np.isfinite(checksum):
        raise RuntimeError("non-finite checksum")
    print(
        f"npb_ep_small checksum={checksum:.6f} rounds={rounds} bins={bins.tolist()} elapsed={elapsed:.3f}s "
        f"pairs_per_s={(pairs * rounds) / max(elapsed, 1e-9):.2f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
