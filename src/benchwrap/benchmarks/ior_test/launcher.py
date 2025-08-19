#!/usr/bin/env python3
import os
import time

import numpy as np

# Define variables of the ini files
# [global]
# api = POSIX
# transferSize = 1m
# blockSize = 64m
# repetitions = 1

transferSizes = [str(2**x) + "m" for x in range(1, 10)]
blocksize = [str(2**x) + "m" for x in range(4, 16)]
print(transferSizes)
print(blocksize)

combinations = []
for ts in transferSizes:
    for bs in blocksize:
        if bs > ts:
            combinations.append((ts, bs))

os.mkdir(f"ior_inis")
os.chdir(f"ior_inis")
for ts, bs in combinations:

    with open(f"ior_ts_{ts}_bs_{bs}.ini", "w") as f:
        f.write(
            f"[global]\napi = POSIX \ntransferSize = {ts}\nblockSize = {bs}\nrepetitions = 10"
        )
