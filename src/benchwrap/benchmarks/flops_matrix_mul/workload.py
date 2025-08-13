#!/usr/bin/env python3
import os
import time

import numpy as np
import psutil

n = 20_000
gb = 2 * n * n * 8 / 1e9
print(f"Allocating two {n}x{n} matrices ≈{gb:.1f} GB", flush=True)


a = np.random.random((n, n))
b = np.random.random((n, n))
print(f"Multiplying on {os.cpu_count()} logical cores …", flush=True)

start_time = time.time()

t0 = time.time()
c = a @ b  # heavy lift: BLAS dgemm
dt = time.time() - t0
print(
    f"GEMM done in {dt:.2f} s → {8*n**3/dt/1e9:.2f} GFLOP/s in time: {time.time() -start_time}",
    flush=True,
)


start_time = time.time()
norm = np.linalg.norm(c)
mem = psutil.virtual_memory().percent
print(
    f" Frobenius = {norm:.3e}\n  RAM usage = {mem}% in time: {time.time() -start_time}"
)  #
