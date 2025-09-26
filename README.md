# Benchmark Suite

**benchwrap** is an energy-aware benchmarking toolkit designed for High Performance Computing (HPC) environments. It provides comprehensive energy consumption analysis and performance profiling through seamless SLURM integration and advanced monitoring tools.
version: 0.3.4
## Features

- **Energy-Aware Benchmarking**: Advanced energy consumption tracking with detailed metrics analysis
- **SLURM Integration**: Comprehensive support for SLURM job submission, monitoring, and accounting
- **LIKWID Performance Monitoring**: Integration with LIKWID-perfctr for hardware performance counters
- **Extensible Benchmark Suite**: Built-in benchmarks for CPU, memory, cache, and I/O performance
- **HDF5 Data Analysis**: Structured data storage and analysis with Jupyter notebooks
- **CLI Interface**: Easy-to-use command-line interface for benchmark management

## Installation

```bash
# Clone the repository
git clone https://github.com/mak8427/benchmark-suite
cd benchmark-suite

# Install in development mode
pip install -e .
```

## Quick Start

1. **List available benchmarks:**
   ```bash
   benchwrap list
   ```

2. **Run a simple benchmark:**
   ```bash
   benchwrap run mem_bandwidth
   ```

3. **Run with specific SLURM configuration:**
   ```bash
   benchwrap run flops_matrix_mul scc-cpu 2
   ```

4. **Add a custom benchmark:**
   ```bash
   benchwrap add my_custom_benchmark.py
   ```

## Usage

### List Available Benchmarks

```bash
benchwrap list
```

### Run a Benchmark

```bash
# Run with default partition
benchwrap run mem_bandwidth

# Run with specific SLURM partition and node count
benchwrap run flops_matrix_mul scc-cpu 2

# Run with explicit options
benchwrap run cache_test -p gpu-partition -n 1
```

### Monitor Job and Analyze Results

After job completion, use the included analysis tools:

```bash
# Generate HDF5 analysis (requires sh5util)
python -c "from benchwrap.executors.utils.benchmarks_func import h5_analysis; h5_analysis('JOBID')"

# View SLURM energy accounting
sacct --format=jobid,elapsed,AveCPUFreq,ConsumedEnergy,ConsumedEnergyRaw -j JOBID
```

### Add Custom Benchmarks

```bash
benchwrap add my_benchmark.py
```

## Built-in Benchmarks

The suite includes several production-ready benchmarks optimized for energy analysis:

### Computational Benchmarks
- **`flops_matrix_mul`** - Double-precision matrix multiplication (DGEMM) with LIKWID profiling
- **`flops_matrix_mul_mini`** - Lightweight matrix multiplication benchmark
- **`flops_matrix_mul_no_likwid`** - Matrix multiplication without performance counter overhead
- **`mem_bandwidth`** - Memory bandwidth testing using AXPY operations
- **`cache_test`** - CPU cache hierarchy performance analysis

### I/O Benchmarks
- **`ior_test`** - Parallel I/O performance using IOR benchmark suite
- **`io_500`** - Comprehensive I/O performance evaluation based on IO-500 benchmark

### Custom Benchmarks
- **`benchmark1`** & **`benchmark2`** - Template benchmarks for custom workloads

Each benchmark includes:
- SLURM job scripts with energy profiling enabled (`--profile=all --acctg-freq=energy=1`)
- LIKWID performance counter integration for hardware metrics
- Structured output for automated analysis

## Energy Analysis & Data Processing

The toolkit provides comprehensive energy analysis capabilities through Jupyter notebooks and HDF5 data processing.

### Energy Metrics

The suite calculates detailed energy efficiency metrics:

| **Metric** | **Description** | **Units** |
|------------|-----------------|-----------|
| **Energy-to-solution (ETS)** | Total energy consumed by the job from start to finish | Joules (J) |
| **Time-to-solution (TTS)** | Total runtime of the job (wall-clock time) | Seconds (s) |
| **Average Power** | Mean power draw during execution (ETS ÷ TTS) | Watts (W) |
| **Peak Power** | Maximum instantaneous power draw observed | Watts (W) |
| **Energy-Delay Product (EDP)** | Combined efficiency metric (ETS × TTS, lower is better) | J·s |
| **Performance/Watt** | Application-specific throughput per unit energy | Varies (e.g., FLOPS/W) |

### Data Analysis Tools

**Jupyter Notebooks** (in `src/data_analysis/`):
- `Energy_Metrics.ipynb` - Comprehensive energy analysis with visualization
- `UserJobProfiling.ipynb` - User-specific job profiling and comparison

**HDF5 Processing**:
- Automatic conversion of SLURM profiling data to structured HDF5 format
- Integration with `sh5util` for SLURM profile data extraction
- Pandas-based analysis workflows for large datasets

### LIKWID Integration

Hardware performance monitoring through LIKWID-perfctr:
- **CPU Performance Counters**: FLOPS, cache misses, memory bandwidth
- **Timeline Profiling**: Power and performance data with temporal resolution
- **Hardware Metrics**: CPU frequency, energy consumption, thermal data

## SLURM Integration

The benchmark suite is designed for SLURM-managed HPC environments and provides:

- **Automatic Job Submission**: Benchmarks are submitted as SLURM jobs with energy profiling enabled
- **Job Monitoring**: Automatic monitoring of job status and completion
- **Energy Tracking**: Integration with SLURM accounting for detailed energy consumption data
- **Resource Management**: Configurable partition, node count, and job parameters
- **Result Processing**: Post-processing of job outputs including HDF5 analysis

### Job Configuration

All benchmarks automatically include energy profiling SLURM directives:
```bash
#SBATCH --profile=all           # Enable comprehensive profiling
#SBATCH --acctg-freq=1          # High-frequency accounting data
#SBATCH --acctg-freq=energy=1   # Energy consumption tracking
```

The repository includes comprehensive SLURM integration tests in `tests/test_slurm.py`:

- **Environment Detection**: Tests verify SLURM availability and graceful degradation
- **Job Submission**: Tests actual SLURM job submission and monitoring workflows
- **Output Validation**: Verifies job outputs and result processing
- **CI Integration**: Automated testing in CI environments with SLURM setup

#### Running SLURM Tests

```bash
# Run all tests (SLURM tests will be skipped if SLURM not available)
pytest tests/

# Run only SLURM tests (requires SLURM environment)
pytest tests/test_slurm.py

# Run with verbose output
pytest tests/test_slurm.py -v
```

### SLURM Testing

### SLURM Requirements

For full functionality, the following tools must be available in the HPC environment:

**Core SLURM Commands:**
- `sbatch` - Job submission with energy profiling support
- `squeue` - Job queue monitoring
- `sinfo` - Partition and node information
- `sacct` - Job accounting and energy consumption data
- `scontrol` - Job control and release operations

**Performance Monitoring Tools:**
- `likwid-perfctr` - Hardware performance counter access
- `sh5util` - SLURM profile data to HDF5 conversion
- Environment modules system for `likwid` module loading

**Python Environment:**
- Conda environment named `energy` (or modify job scripts accordingly)
- All dependencies from `requirements.txt` installed

## Architecture

The toolkit is organized into several key components:

```
src/benchwrap/
├── cli.py                    # Command-line interface
├── core.py                   # Core benchmark management logic
├── benchmarks/               # Benchmark workloads and SLURM scripts
│   ├── mem_bandwidth/        # Memory bandwidth benchmark
│   ├── flops_matrix_mul/     # Matrix multiplication benchmarks
│   ├── cache_test/           # Cache performance tests
│   └── ...
├── executors/                # Benchmark execution modules
│   ├── mem_bandwidth.py      # Memory bandwidth executor
│   ├── flops_matrix_mul.py   # FLOPS benchmark executor
│   └── utils/
│       └── benchmarks_func.py # Core SLURM and analysis functions
└── data_analysis/            # Jupyter notebooks for energy analysis
    ├── Energy_Metrics.ipynb  # Comprehensive energy analysis
    └── UserJobProfiling.ipynb # User job profiling tools
```

### Workflow

1. **Job Submission**: `benchwrap run` → `sbatch_launch()` → SLURM job queue
2. **Execution**: SLURM executes `job_start.sh` with LIKWID profiling
3. **Data Collection**: Energy, performance counters, and timing data captured
4. **Analysis**: HDF5 conversion and Jupyter notebook analysis tools

## Development

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Running Tests

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

### Pre-commit Hooks

The project uses GitHub Actions for continuous integration with comprehensive testing:

- **Unit Tests**: Core functionality testing
- **SLURM Integration**: Full SLURM workflow testing with mock SLURM environment
- **Build Testing**: Package building and distribution validation
- **Code Quality**: Linting and formatting checks

The SLURM CI job (`cli-slurm`) specifically tests:
- SLURM command availability
- Job submission and monitoring
- Output validation
- Benchmark suite integration

## CI/CD

## License

This project is available under an open source license. See the repository for license details.
