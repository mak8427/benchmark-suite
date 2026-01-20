#!/usr/bin/env python3
"""STREAM-like triad for memory bandwidth."""
import os
import time

import numpy as np

n = int(os.getenv("STREAM_SIZE", "50000000"))
iters = int(os.getenv("STREAM_ITERS", "10"))
scalar = float(os.getenv("STREAM_SCALAR", "3.0"))

print(f"Allocating arrays of {n} float64 elements", flush=True)
a = np.random.random(n)
b = np.random.random(n)
c = np.random.random(n)

# Warm up
_ = b + scalar * c

start = time.time()
for _ in range(iters):
    a = b + scalar * c
end = time.time()

elapsed = end - start
bytes_moved = 3 * 8 * n * iters
print(f"Triad: {iters} iters in {elapsed:.2f}s", flush=True)
print(f"Approx BW: {bytes_moved / elapsed / 1e9:.2f} GB/s")
