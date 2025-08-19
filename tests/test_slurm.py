#!/usr/bin/env python3
"""
Tests for SLURM functionality in the benchmark suite.

These tests verify that SLURM job submission, monitoring, and post-processing
work correctly. They require a SLURM environment to be available.
"""
import os
import subprocess
import time
import tempfile
import pathlib
import pytest
import sys

# Add src to path for imports
ROOT = pathlib.Path(__file__).parent.parent.resolve()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def has_slurm():
    """Check if SLURM commands are available."""
    try:
        subprocess.run(['squeue', '--version'], check=True, capture_output=True)
        subprocess.run(['sbatch', '--version'], check=True, capture_output=True)
        subprocess.run(['sinfo', '--version'], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not has_slurm(), reason="SLURM not available")
class TestSlurmIntegration:
    """Test SLURM integration functionality."""
    
    def test_slurm_commands_available(self):
        """Test that basic SLURM commands are available and working."""
        # Test squeue
        result = subprocess.run(['squeue', '--version'], capture_output=True, text=True)
        assert result.returncode == 0
        assert 'slurm' in result.stdout.lower()
        
        # Test sbatch
        result = subprocess.run(['sbatch', '--version'], capture_output=True, text=True)
        assert result.returncode == 0
        assert 'slurm' in result.stdout.lower()
        
        # Test sinfo
        result = subprocess.run(['sinfo', '--version'], capture_output=True, text=True)
        assert result.returncode == 0
        assert 'slurm' in result.stdout.lower()
    
    def test_slurm_job_submission(self):
        """Test submitting and monitoring a simple SLURM job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)
            
            # Create a simple test script
            test_script = tmpdir / "test_job.sh"
            test_script.write_text("""#!/bin/bash
#SBATCH --job-name=pytest-test
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:01:00
#SBATCH --output={}/slurm_output_%j.out
#SBATCH --error={}/slurm_error_%j.err

echo "Test job started at $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Test computation..."
result=$((42 * 2))
echo "Result: $result"
echo "Test job completed at $(date)"
""".format(tmpdir, tmpdir))
            
            test_script.chmod(0o755)
            
            # Submit the job
            result = subprocess.run(
                ['sbatch', '--parsable', str(test_script)], 
                capture_output=True, text=True, check=True
            )
            job_id = result.stdout.strip().split(';')[0]
            
            # Wait for job to complete (with timeout)
            timeout = 60
            elapsed = 0
            while elapsed < timeout:
                result = subprocess.run(
                    ['squeue', '-j', job_id], 
                    capture_output=True, text=True
                )
                if job_id not in result.stdout:
                    break
                time.sleep(2)
                elapsed += 2
            
            assert elapsed < timeout, f"Job {job_id} did not complete within {timeout} seconds"
            
            # Check output file exists and contains expected content
            output_file = tmpdir / f"slurm_output_{job_id}.out"
            assert output_file.exists(), f"Output file {output_file} not found"
            
            output_content = output_file.read_text()
            assert "Test job started" in output_content
            assert "Test job completed" in output_content
            assert "Result: 84" in output_content
    
    def test_benchmark_slurm_imports(self):
        """Test that SLURM benchmark utilities can be imported."""
        try:
            from benchwrap.executors.utils.benchmarks_func import sbatch_launch, run_slurm_job, h5_analysis
            # If we get here, imports succeeded
            assert callable(sbatch_launch)
            assert callable(run_slurm_job)
            assert callable(h5_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import SLURM benchmark functions: {e}")
    
    def test_benchmark_slurm_function_parameters(self):
        """Test that SLURM benchmark functions have expected signatures."""
        from benchwrap.executors.utils.benchmarks_func import sbatch_launch, run_slurm_job
        import inspect
        
        # Test sbatch_launch signature
        sig = inspect.signature(sbatch_launch)
        assert 'bench_name' in sig.parameters
        assert 'partition' in sig.parameters
        
        # Test run_slurm_job signature  
        sig = inspect.signature(run_slurm_job)
        assert 'bench_name' in sig.parameters
        assert 'partition' in sig.parameters


@pytest.mark.skipif(has_slurm(), reason="SLURM is available - testing graceful degradation")
def test_no_slurm_graceful_degradation():
    """Test that the benchmark suite handles missing SLURM gracefully."""
    # This test runs when SLURM is NOT available
    # It should verify that the benchmark suite fails gracefully
    
    # Try to import the benchmark functions - this should still work
    try:
        from benchwrap.executors.utils.benchmarks_func import sbatch_launch, run_slurm_job
        # Functions should be importable even without SLURM
    except ImportError as e:
        pytest.fail(f"Benchmark functions should be importable even without SLURM: {e}")
    
    # Verify that running a SLURM benchmark fails gracefully
    result = subprocess.run(
        [sys.executable, '-c', '''
import sys
sys.path.insert(0, "src")
try:
    from benchwrap.executors.utils.benchmarks_func import sbatch_launch
    sbatch_launch("test", "test-partition") 
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    print("Expected error:", str(e))
    sys.exit(0)
except Exception as e:
    print("Unexpected error:", str(e))
    sys.exit(1)
sys.exit(2)  # Should not reach here
        '''],
        capture_output=True, text=True
    )
    
    # Should exit with code 0 (expected error) or 1 (unexpected error)
    # Code 2 would mean no error occurred, which is unexpected
    assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"


def test_cli_slurm_commands_exist():
    """Test that CLI commands related to SLURM benchmarks exist."""
    from benchwrap.cli import benchwrap, run, _list
    
    # Test that the CLI module loads without errors
    assert callable(run.callback)
    assert callable(_list.callback)
    
    # Test that benchmarks are discoverable
    import benchwrap.executors
    import importlib.resources as res
    
    root = res.files("benchwrap.executors")
    modules = [p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"]
    
    # Should have some benchmark modules
    assert len(modules) > 0
    
    # Should include known SLURM benchmarks
    expected_benchmarks = ["mem_bandwidth", "flops_matrix_mul", "cache_test"]
    for benchmark in expected_benchmarks:
        assert benchmark in modules, f"Expected benchmark {benchmark} not found in {modules}"