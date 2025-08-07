#!/usr/bin/env python3
# 2. Cache Hierarchy Test
import numpy as np, time
sizes = [2**i for i in range(10, 25)]  # 1KB to 32MB
times = []

for sz in sizes:
    a = np.random.rand(sz)
    # Touch memory to load into cache
    a.sum()
    start = time.time()
    # Strided access to defeat prefetch
    for _ in range(100):
        a[::4] += 1  # 16-byte stride on 64-bit systems
    times.append((sz, time.time()-start))
print("Cache test complete:", times[-3:])  # Show large-size results