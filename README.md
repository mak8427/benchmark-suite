# benchwrap

version: 0.3.17

`benchwrap` is a command-line wrapper for running energy-aware benchmark workloads on Slurm clusters and syncing the resulting profiling artifacts to the backend.

## Quick Start

```bash
benchwrap list
benchwrap describe flops_matrix_mul_mini
benchwrap run flops_matrix_mul_mini -p medium -n 1
benchwrap sync
```

The package includes built-in benchmark executors, Slurm `job_start.sh` scripts, benchmark descriptions, and shell completions for common shells.
