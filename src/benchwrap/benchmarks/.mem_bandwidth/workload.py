#!/usr/bin/env python3
# 1. Memory Bandwidth Test (AXPY variant)
import time

import numpy as np

n = 2**28  # ~268 million elements (2GB array)
x = np.random.rand(n)
y = np.random.rand(n)
alpha = 2.0

# Cache warming
np.add(alpha * x, y)

start = time.time()
np.add(alpha * x, y)  # 2n reads + n writes
duration = time.time() - start
gb = (3 * 8 * n) / 1e9  # GB moved
print(f"Memory BW: {gb/duration:.2f} GB/s")
