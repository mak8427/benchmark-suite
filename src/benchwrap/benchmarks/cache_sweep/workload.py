#!/usr/bin/env python3
"""Cache hierarchy sweep over working-set sizes."""
import os
import time

import numpy as np

min_pow = int(os.getenv("CACHE_MIN_POW", "10"))
max_pow = int(os.getenv("CACHE_MAX_POW", "28"))
iters = int(os.getenv("CACHE_ITERS", "100"))
stride = int(os.getenv("CACHE_STRIDE", "4"))

sizes = [2**p for p in range(min_pow, max_pow + 1)]
print("size_bytes,seconds", flush=True)
for sz in sizes:
    elems = max(1, sz // 8)
    a = np.random.random(elems)
    a.sum()
    start = time.time()
    for _ in range(iters):
        a[::stride] += 1
    elapsed = time.time() - start
    print(f"{sz},{elapsed:.6f}", flush=True)
