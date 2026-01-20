#!/usr/bin/env python3
"""Branch-heavy integer loop."""
import os
import time

import numpy as np

n = int(os.getenv("BRANCHY_N", "5000000"))
reps = int(os.getenv("BRANCHY_REPS", "3"))

print(f"Generating {n} random int64 values", flush=True)
data = np.random.randint(0, 1_000_000, size=n, dtype=np.int64)

start = time.time()
acc = 0
for _ in range(reps):
    for v in data:
        if v & 1:
            acc += v
        else:
            acc -= v
elapsed = time.time() - start

ops = n * reps
print(f"Branchy loop: {ops} iters in {elapsed:.2f}s", flush=True)
print(f"Ops/s: {ops / elapsed:.2f}")
print(f"Checksum: {acc}")
