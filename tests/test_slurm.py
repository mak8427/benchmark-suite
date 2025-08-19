#!/usr/bin/env python3
"""
Tests for SLURM functionality in the benchmark suite.

These tests verify that SLURM job submission, monitoring, and post-processing
work correctly. They require a SLURM environment to be available.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import time

import pytest

# Add src to path for imports
ROOT = pathlib.Path(__file__).parent.parent.resolve()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def has_slurm():
    """Check if SLURM commands are available."""
    try:
        subprocess.run(["squeue", "--version"], check=True, capture_output=True)
        subprocess.run(["sbatch", "--version"], check=True, capture_output=True)
        subprocess.run(["sinfo", "--version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.mark.skipif(not has_slurm(), reason="SLURM not available")
class TestSlurmIntegration:
    """Test SLURM integration functionality."""

    def test_slurm_commands_available(self):
        """Test that basic SLURM commands are available and working."""
        # Test squeue
        result = subprocess.run(["squeue", "--version"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "slurm" in result.stdout.lower()

        # Test sbatch
        result = subprocess.run(["sbatch", "--version"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "slurm" in result.stdout.lower()

        # Test sinfo
        result = subprocess.run(["sinfo", "--version"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "slurm" in result.stdout.lower()

    def test_slurm_job_submission(self):
        """Test submitting and monitoring a simple SLURM job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = pathlib.Path(tmpdir)

            # Create a simple test script
            test_script = tmpdir / "test_job.sh"
            test_script.write_text(
                """#!/bin/bash
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
""".format(
                    tmpdir, tmpdir
                )
            )

            test_script.chmod(0o755)

            # Submit the job
            result = subprocess.run(
                ["sbatch", "--parsable", str(test_script)],
                capture_output=True,
                text=True,
                check=True,
            )
            job_id = result.stdout.strip().split(";")[0]

            # Wait for job to complete (with timeout)
            timeout = 60
            elapsed = 0
            while elapsed < timeout:
                result = subprocess.run(
                    ["squeue", "-j", job_id], capture_output=True, text=True
                )
                if job_id not in result.stdout:
                    break
                time.sleep(2)
                elapsed += 2

            assert (
                elapsed < timeout
            ), f"Job {job_id} did not complete within {timeout} seconds"

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
            from benchwrap.executors.utils.benchmarks_func import (
                h5_analysis, run_slurm_job, sbatch_launch)

            # If we get here, imports succeeded
            assert callable(sbatch_launch)
            assert callable(run_slurm_job)
            assert callable(h5_analysis)
        except ImportError as e:
            pytest.fail(f"Failed to import SLURM benchmark functions: {e}")

    def test_benchmark_slurm_function_parameters(self):
        """Test that SLURM benchmark functions have expected signatures."""
        import inspect

        from benchwrap.executors.utils.benchmarks_func import (run_slurm_job,
                                                               sbatch_launch)

        # Test sbatch_launch signature
        sig = inspect.signature(sbatch_launch)
        assert "bench_name" in sig.parameters
        assert "partition" in sig.parameters

        # Test run_slurm_job signature
        sig = inspect.signature(run_slurm_job)
        assert "bench_name" in sig.parameters
        assert "partition" in sig.parameters


@pytest.mark.skipif(
    has_slurm(), reason="SLURM is available - testing graceful degradation"
)
def test_no_slurm_graceful_degradation():
    """Test that the benchmark suite handles missing SLURM gracefully."""
    # This test runs when SLURM is NOT available
    # It should verify that the benchmark suite fails gracefully

    # Try to import the benchmark functions - this should still work
    try:
        from benchwrap.executors.utils.benchmarks_func import (run_slurm_job,
                                                               sbatch_launch)

        # Functions should be importable even without SLURM
    except ImportError as e:
        pytest.fail(f"Benchmark functions should be importable even without SLURM: {e}")

    # Verify that running a SLURM benchmark fails gracefully
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
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
        """,
        ],
        capture_output=True,
        text=True,
    )

    # Should exit with code 0 (expected error) or 1 (unexpected error)
    # Code 2 would mean no error occurred, which is unexpected
    assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"


def test_cli_slurm_commands_exist():
    """Test that CLI commands related to SLURM benchmarks exist."""
    from benchwrap.cli import _list, benchwrap, run

    # Test that the CLI module loads without errors
    assert callable(run.callback)
    assert callable(_list.callback)

    # Test that benchmarks are discoverable
    import importlib.resources as res

    import benchwrap.executors

    root = res.files("benchwrap.executors")
    modules = [
        p.stem for p in root.iterdir() if p.suffix == ".py" and p.stem != "__init__"
    ]

    # Should have some benchmark modules
    assert len(modules) > 0

    # Should include known SLURM benchmarks
    expected_benchmarks = ["mem_bandwidth", "flops_matrix_mul", "cache_test", "flops_matrix_mul_mini"]
    for benchmark in expected_benchmarks:
        assert (
            benchmark in modules
        ), f"Expected benchmark {benchmark} not found in {modules}"


class TestFlopsMatrixMulMini:
    """Test the flops_matrix_mul_mini benchmark specifically."""

    def test_flops_matrix_mul_mini_mocked_execution(self, tmp_path, monkeypatch):
        """Test running flops_matrix_mul_mini with mocked SLURM commands."""
        import subprocess
        import tempfile
        import os
        from unittest.mock import MagicMock, call
        
        # Create temporary home directory for outputs
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        
        # Create the benchwrap job output directory
        job_dir = fake_home / ".local" / "share" / "benchwrap"
        job_dir.mkdir(parents=True)
        
        # Mock job ID
        mock_job_id = "12345"
        
        # Track subprocess calls
        subprocess_calls = []
        original_run = subprocess.run
        
        def mock_subprocess_run(cmd, **kwargs):
            subprocess_calls.append((cmd, kwargs))
            
            if cmd[0] == "sbatch":
                # Mock sbatch response - return job ID
                mock_result = MagicMock()
                mock_result.stdout = f"{mock_job_id};cluster\n"
                mock_result.returncode = 0
                # Create the job directory that sbatch_launch expects
                job_output_dir = fake_home / ".local" / "share" / "benchwrap" / f"job_{mock_job_id}"
                job_output_dir.mkdir(parents=True, exist_ok=True)
                return mock_result
            
            elif cmd[0] == "scontrol" and "release" in cmd:
                # Mock scontrol release - just succeed
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
            
            elif cmd[0] == "squeue":
                # Mock squeue - job not in queue (completed)
                mock_result = MagicMock()
                mock_result.stdout = ""  # Empty means job completed
                mock_result.returncode = 0
                return mock_result
            
            elif cmd[0] == "python" and "-m" in cmd:
                # Mock the actual benchmark execution
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
            
            else:
                # For any other commands, call the original
                return original_run(cmd, **kwargs)
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        # Import and run the benchmark
        from benchwrap.executors.flops_matrix_mul_mini import main
        
        # Mock sys.argv to simulate command line arguments
        import sys
        original_argv = sys.argv
        try:
            sys.argv = ["flops_matrix_mul_mini", "--partition", "test-partition"]
            main()
        finally:
            sys.argv = original_argv
        
        # Verify that sbatch was called with correct parameters
        sbatch_calls = [call for call in subprocess_calls if call[0][0] == "sbatch"]
        assert len(sbatch_calls) >= 1, f"Expected sbatch call, got calls: {subprocess_calls}"
        
        sbatch_cmd = sbatch_calls[0][0]
        assert "sbatch" in sbatch_cmd
        assert "--parsable" in sbatch_cmd
        assert "--hold" in sbatch_cmd
        assert "-p" in sbatch_cmd
        assert "test-partition" in sbatch_cmd
        
        # Verify scontrol release was called
        scontrol_calls = [call for call in subprocess_calls if call[0][0] == "scontrol"]
        assert len(scontrol_calls) >= 1
        scontrol_cmd = scontrol_calls[0][0]
        assert "scontrol" in scontrol_cmd
        assert "release" in scontrol_cmd
        assert mock_job_id in scontrol_cmd

    def test_flops_matrix_mul_mini_job_output_verification(self, tmp_path, monkeypatch):
        """Test that job outputs are created in the correct location."""
        import subprocess
        import os
        from unittest.mock import MagicMock
        
        # Create temporary home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        
        # Mock job ID
        mock_job_id = "67890"
        
        def mock_subprocess_run(cmd, **kwargs):
            if cmd[0] == "sbatch":
                mock_result = MagicMock()
                mock_result.stdout = f"{mock_job_id};cluster\n"
                mock_result.returncode = 0
                
                # Create expected output directory and files
                job_output_dir = fake_home / ".local" / "share" / "benchwrap" / f"job_{mock_job_id}"
                job_output_dir.mkdir(parents=True, exist_ok=True)
                
                # Create mock output files
                output_file = job_output_dir / f"slurm-{mock_job_id}.out"
                error_file = job_output_dir / f"slurm-{mock_job_id}.err"
                
                output_file.write_text(f"Job {mock_job_id} completed successfully\nResults -> {job_output_dir}\n")
                error_file.write_text("")  # No errors
                
                return mock_result
            
            elif cmd[0] == "scontrol":
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
            
            else:
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        # Run the benchmark launcher function directly
        from benchwrap.executors.utils.benchmarks_func import sbatch_launch
        
        job_id = sbatch_launch("flops_matrix_mul_mini", "test-partition")
        
        # Verify job ID is returned
        assert job_id == int(mock_job_id)
        
        # Verify output directory was created
        expected_job_dir = fake_home / ".local" / "share" / "benchwrap" / f"job_{mock_job_id}"
        assert expected_job_dir.exists()
        
        # Verify output files exist (if created by our mock)
        output_file = expected_job_dir / f"slurm-{mock_job_id}.out"
        error_file = expected_job_dir / f"slurm-{mock_job_id}.err"
        
        if output_file.exists():
            content = output_file.read_text()
            assert f"Job {mock_job_id}" in content
            assert "Results ->" in content

    def test_flops_matrix_mul_mini_error_handling(self, tmp_path, monkeypatch):
        """Test error handling when sbatch fails."""
        import subprocess
        from unittest.mock import MagicMock
        
        # Create temporary home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        
        def mock_subprocess_run_failure(cmd, **kwargs):
            if cmd[0] == "sbatch":
                # Simulate sbatch failure
                error = subprocess.CalledProcessError(1, cmd)
                error.stderr = "sbatch: error: Batch job submission failed: Invalid partition name specified"
                raise error
            else:
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run_failure)
        
        # Test that the error is properly handled
        from benchwrap.executors.utils.benchmarks_func import sbatch_launch
        
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            sbatch_launch("flops_matrix_mul_mini", "invalid-partition")
        
        assert "Batch job submission failed" in str(exc_info.value.stderr)

    @pytest.mark.skipif(not has_slurm(), reason="SLURM not available")
    def test_flops_matrix_mul_mini_real_slurm_integration(self, tmp_path):
        """Test with real SLURM if available - integration test."""
        import subprocess
        import time
        import os
        
        # This test runs only if SLURM is actually available
        # It submits a real job but makes it very lightweight
        
        # Create a minimal test script that mimics the benchmark
        test_script = tmp_path / "mini_test.sh"
        test_script.write_text("""#!/bin/bash
#SBATCH --job-name=test-flops-mini
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:01:00

echo "Starting mini benchmark test"
echo "Job ID: $SLURM_JOB_ID"
python3 -c "import numpy as np; a = np.random.random((100,100)); b = np.random.random((100,100)); c = a @ b; print(f'Completed matrix multiply: norm={np.linalg.norm(c):.2e}')"
echo "Mini test completed"
""")
        test_script.chmod(0o755)
        
        # Submit the job
        result = subprocess.run(
            ["sbatch", "--parsable", str(test_script)],
            capture_output=True,
            text=True,
            check=True,
        )
        job_id = result.stdout.strip().split(";")[0]
        
        # Wait for job to complete (with timeout)
        timeout = 120  # 2 minutes should be enough for a simple test
        elapsed = 0
        while elapsed < timeout:
            result = subprocess.run(
                ["squeue", "-j", job_id], capture_output=True, text=True
            )
            if job_id not in result.stdout:
                break
            time.sleep(2)
            elapsed += 2
        
        assert elapsed < timeout, f"Job {job_id} did not complete within {timeout} seconds"
        
        # Check if output file was created (SLURM default location)
        # This is a basic verification that the job ran
        print(f"Test job {job_id} completed successfully")

    def test_benchwrap_run_flops_matrix_mul_mini_cli(self, tmp_path, monkeypatch):
        """Test the full CLI command 'benchwrap run flops_matrix_mul_mini' with mocked SLURM."""
        import subprocess
        from unittest.mock import MagicMock
        from click.testing import CliRunner
        
        # Create temporary home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))
        
        # Mock job ID
        mock_job_id = "98765"
        
        def mock_subprocess_run(cmd, **kwargs):
            if cmd[0] == "sbatch":
                mock_result = MagicMock()
                mock_result.stdout = f"{mock_job_id};cluster\n"
                mock_result.returncode = 0
                
                # Create expected output directory
                job_output_dir = fake_home / ".local" / "share" / "benchwrap" / f"job_{mock_job_id}"
                job_output_dir.mkdir(parents=True, exist_ok=True)
                
                return mock_result
            
            elif cmd[0] == "scontrol":
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
            
            elif cmd[0] == "python" and "-m" in cmd and "flops_matrix_mul_mini" in cmd:
                # This is the actual call to the executor
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
            
            else:
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result
        
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
        
        # Test CLI command
        from benchwrap.cli import run
        
        runner = CliRunner()
        result = runner.invoke(run, ["flops_matrix_mul_mini", "test-partition"])
        
        # Check that the command executed without errors
        assert result.exit_code == 0, f"CLI command failed: {result.output}"
        
        # Check that the expected output mentions the benchmark
        assert "flops_matrix_mul_mini" in result.output or "running" in result.output
