#!/usr/bin/env python3
"""Mixed compute+memory phases to measure average energy efficiency."""
import os
import time

import numpy as np

n = int(os.getenv("MIXED_SIZE", "20000000"))
phases = int(os.getenv("MIXED_PHASES", "5"))
comp_iters = int(os.getenv("MIXED_COMP_ITERS", "20"))
mem_iters = int(os.getenv("MIXED_MEM_ITERS", "20"))

print(f"Allocating arrays of {n} float64 elements", flush=True)
a = np.random.random(n)
b = np.random.random(n)
c = np.random.random(n)

for i in range(phases):
    start = time.time()
    for _ in range(comp_iters):
        a = np.add(a * b, c)
    comp_time = time.time() - start

    start = time.time()
    for _ in range(mem_iters):
        a[:] = b
    mem_time = time.time() - start

    print(
        f"phase={i},compute_s={comp_time:.3f},mem_s={mem_time:.3f}",
        flush=True,
    )
