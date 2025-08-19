# Benchmark Suite

An energy-aware benchmark helper for HPC environments with SLURM support.

## Features

- **SLURM Integration**: Comprehensive support for SLURM job submission and monitoring
- **Energy Monitoring**: Track energy consumption during benchmark execution
- **Extensible Benchmarks**: Built-in benchmarks for CPU, memory, and I/O performance
- **CLI Interface**: Easy-to-use command-line interface for benchmark management

## Installation

```bash
pip install -e .
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

# Run with specific SLURM partition
benchwrap run mem_bandwidth scc-cpu
```

### Add Custom Benchmarks

```bash
benchwrap add my_benchmark.py
```

## Built-in Benchmarks

- `mem_bandwidth` - Memory bandwidth testing using AXPY operations
- `flops_matrix_mul` - Floating-point operations per second using matrix multiplication  
- `cache_test` - Cache performance testing
- `ior_test` - I/O performance testing

## SLURM Integration

The benchmark suite is designed for SLURM-managed HPC environments and provides:

- **Automatic Job Submission**: Benchmarks are submitted as SLURM jobs with appropriate resource requests
- **Job Monitoring**: Automatic monitoring of job status and completion
- **Energy Tracking**: Integration with SLURM accounting for energy consumption data
- **Result Processing**: Post-processing of job outputs including HDF5 analysis

### SLURM Testing

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

### SLURM Requirements

For full functionality, the following SLURM tools must be available:

- `sbatch` - Job submission
- `squeue` - Job queue monitoring  
- `sinfo` - Partition information
- `sacct` - Job accounting data
- `scontrol` - Job control

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## CI/CD

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

## License

[Add license information here]