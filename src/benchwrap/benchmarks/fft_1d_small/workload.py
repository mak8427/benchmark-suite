#!/usr/bin/env python3
"""Short 1D FFT benchmark with deterministic validation."""

from __future__ import annotations

import os
import time

import numpy as np


def main() -> None:
    size = int(os.getenv("FFT_SIZE", "1048576"))
    iters = int(os.getenv("FFT_ITERS", "24"))
    target_seconds = float(os.getenv("FFT_SECONDS", "30"))
    rng = np.random.default_rng(12345)
    signal = rng.random(size) + 1j * rng.random(size)
    original_norm = float(np.linalg.norm(signal))

    print(
        f"fft_1d_small size={size} iters={iters} target_seconds={target_seconds}",
        flush=True,
    )
    start = time.time()
    checksum = 0.0
    rounds = 0
    while time.time() - start < target_seconds:
        for step in range(iters):
            spectrum = np.fft.fft(signal)
            signal = np.fft.ifft(spectrum)
            checksum += float(np.abs(spectrum[(step + rounds) % size]))
            signal *= 1.0 + (step % 3) * 1e-12
        rounds += 1

    elapsed = time.time() - start
    residual = abs(float(np.linalg.norm(signal)) - original_norm) / max(original_norm, 1e-12)
    if residual > 1e-6:
        raise RuntimeError(f"fft residual too high: {residual}")
    flops_est = 10.0 * size * np.log2(size) * iters * rounds * 2.0
    print(
        f"fft_1d_small checksum={checksum:.6f} rounds={rounds} residual={residual:.3e} elapsed={elapsed:.3f}s "
        f"estimated_gflops={flops_est / max(elapsed, 1e-9) / 1e9:.2f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
