#!/usr/bin/env python3
"""AVX-512-ish FMA throughput using NumPy vector ops.

Uses a*b + c in a tight loop to drive SIMD/FMA units via BLAS/NumPy.
"""
import os
import time

import numpy as np

n = int(os.getenv("AVX_SIZE", "20000000"))
iters = int(os.getenv("AVX_ITERS", "50"))

print(f"Allocating arrays of {n} float64 elements", flush=True)
a = np.random.random(n)
b = np.random.random(n)
c = np.random.random(n)

# Warm up
np.add(a * b, c)

start = time.time()
for _ in range(iters):
    a = np.add(a * b, c)
end = time.time()

elapsed = end - start
flops = 2 * n * iters
print(f"FMA loop: {iters} iters in {elapsed:.2f}s", flush=True)
print(f"Approx GFLOP/s: {flops / elapsed / 1e9:.2f}")
