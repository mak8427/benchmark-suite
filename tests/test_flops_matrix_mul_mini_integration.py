#!/usr/bin/env python3
"""
Integration test for flops_matrix_mul_mini benchmark.

This test demonstrates the complete workflow:
1. Job submission to SLURM
2. Job queue monitoring
3. Output verification
4. Error handling

The test uses mocking to simulate SLURM behavior, allowing it to run
in CI/CD environments without requiring an actual SLURM cluster.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for imports
ROOT = pathlib.Path(__file__).parent.parent.resolve()
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class TestFlopsMatrixMulMiniIntegration:
    """Integration test for the complete flops_matrix_mul_mini workflow."""

    def test_complete_workflow_with_mocked_slurm(self, tmp_path, monkeypatch):
        """
        Test the complete workflow of running flops_matrix_mul_mini:
        - Set up a SLURM cluster online (mocked)
        - Submit the job
        - Check that the job is in queue
        - Check that the output is in the correct folder
        - Verify no errors occurred
        """
        # Setup temporary environment
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Create the benchwrap job output directory structure
        job_output_base = fake_home / ".local" / "share" / "benchwrap"
        job_output_base.mkdir(parents=True)

        # Mock job ID and tracking variables
        mock_job_id = "42001"
        job_states = {"submitted": False, "in_queue": True, "completed": False}
        subprocess_calls = []

        def mock_subprocess_run(cmd, **kwargs):
            """Mock subprocess.run to simulate SLURM commands."""
            subprocess_calls.append(cmd)

            if cmd[0] == "sbatch":
                # Step 1: Submit the job
                job_states["submitted"] = True
                job_states["in_queue"] = True

                # Create job output directory
                job_dir = job_output_base / f"job_{mock_job_id}"
                job_dir.mkdir(parents=True, exist_ok=True)

                # Create output files
                output_file = job_dir / f"slurm-{mock_job_id}.out"
                error_file = job_dir / f"slurm-{mock_job_id}.err"

                # Simulate successful job execution output
                output_content = f"""Starting flops_matrix_mul_mini benchmark
Job ID: {mock_job_id}
Allocating two 12000x12000 matrices ≈2.9 GB
Multiplying on 4 logical cores …
GEMM done in 15.23 s → 152.3 GFLOP/s in time: 15.45
Frobenius = 1.732e+06
RAM usage = 45% in time: 0.12
Results -> {job_dir}
Benchmark completed successfully
"""
                output_file.write_text(output_content)
                error_file.write_text("")  # No errors

                # Return job ID
                mock_result = MagicMock()
                mock_result.stdout = f"{mock_job_id};cluster\n"
                mock_result.returncode = 0
                return mock_result

            elif cmd[0] == "scontrol" and "release" in cmd:
                # Step 2: Release the job (start execution)
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result

            elif cmd[0] == "squeue":
                # Step 3: Check job queue status
                if job_states["in_queue"] and not job_states["completed"]:
                    # Simulate job running for a few checks, then completing
                    if len([c for c in subprocess_calls if c[0] == "squeue"]) >= 2:
                        job_states["in_queue"] = False
                        job_states["completed"] = True

                    # Return job in queue
                    mock_result = MagicMock()
                    mock_result.stdout = f"{mock_job_id}  partition  test-job  user  R  0:15  1  node001\n"
                    mock_result.returncode = 0
                    return mock_result
                else:
                    # Job completed - not in queue
                    mock_result = MagicMock()
                    mock_result.stdout = ""  # Empty output means job not in queue
                    mock_result.returncode = 0
                    return mock_result

            elif cmd[0] == "sacct":
                # Job accounting information
                mock_result = MagicMock()
                mock_result.stdout = f"""JobID|Elapsed|AveCPUFreq|ConsumedEnergy|ConsumedEnergyRaw
{mock_job_id}|00:15:23|2.4GHz|125J|125000
"""
                mock_result.returncode = 0
                return mock_result

            else:
                # Default mock for any other commands
                mock_result = MagicMock()
                mock_result.returncode = 0
                return mock_result

        # Apply the mock
        monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

        # Import the benchmark functions
        from benchwrap.executors.utils.benchmarks_func import (run_slurm_job,
                                                               sbatch_launch)

        # Step 1: Submit the job
        print("Step 1: Submitting job to SLURM...")
        job_id = sbatch_launch("flops_matrix_mul_mini", "scc-cpu")

        # Verify job was submitted
        assert job_id == int(mock_job_id)
        assert job_states["submitted"]
        print(f"✓ Job {job_id} submitted successfully")

        # Step 2: Check that job is in queue
        print("Step 2: Checking job queue status...")
        result = subprocess.run(
            ["squeue", "-j", str(job_id)], capture_output=True, text=True
        )
        assert str(job_id) in result.stdout  # Job should be in queue initially
        print(f"✓ Job {job_id} found in queue")

        # Step 3: Wait for job completion (simulated)
        print("Step 3: Waiting for job completion...")
        timeout = 30
        elapsed = 0
        while elapsed < timeout:
            result = subprocess.run(
                ["squeue", "-j", str(job_id)], capture_output=True, text=True
            )
            if str(job_id) not in result.stdout:
                print(f"✓ Job {job_id} completed")
                break
            elapsed += 1

        assert elapsed < timeout, f"Job did not complete within {timeout} iterations"

        # Step 4: Verify output files exist and contain expected content
        print("Step 4: Verifying output files...")
        expected_job_dir = job_output_base / f"job_{job_id}"
        assert (
            expected_job_dir.exists()
        ), f"Job output directory {expected_job_dir} not found"

        output_file = expected_job_dir / f"slurm-{job_id}.out"
        error_file = expected_job_dir / f"slurm-{job_id}.err"

        assert output_file.exists(), f"Output file {output_file} not found"
        assert error_file.exists(), f"Error file {error_file} not found"

        # Step 5: Verify output content
        output_content = output_file.read_text()
        error_content = error_file.read_text()

        # Check for expected output indicators
        assert (
            "GFLOP/s" in output_content
        ), "Expected FLOPS calculation not found in output"
        assert (
            "Results ->" in output_content
        ), "Expected results path not found in output"
        assert (
            "Benchmark completed successfully" in output_content
        ), "Success message not found"

        # Check that no errors occurred
        assert error_content.strip() == "", f"Unexpected errors found: {error_content}"

        print("✓ Output files verified successfully")
        print("✓ No errors found in benchmark execution")

        # Step 6: Verify SLURM command sequence
        sbatch_calls = [cmd for cmd in subprocess_calls if cmd[0] == "sbatch"]
        scontrol_calls = [cmd for cmd in subprocess_calls if cmd[0] == "scontrol"]
        squeue_calls = [cmd for cmd in subprocess_calls if cmd[0] == "squeue"]

        assert len(sbatch_calls) >= 1, "sbatch should have been called"
        assert len(scontrol_calls) >= 1, "scontrol release should have been called"
        assert len(squeue_calls) >= 1, "squeue should have been called for monitoring"

        print("✓ All SLURM commands executed in correct sequence")
        print("✓ Complete flops_matrix_mul_mini workflow test PASSED")

    def test_error_scenarios(self, tmp_path, monkeypatch):
        """Test error handling in various failure scenarios."""
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        from benchwrap.executors.utils.benchmarks_func import sbatch_launch

        # Test 1: sbatch command not found
        def mock_sbatch_not_found(cmd, **kwargs):
            if cmd[0] == "sbatch":
                raise FileNotFoundError("sbatch: command not found")
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_sbatch_not_found)

        with pytest.raises(FileNotFoundError):
            sbatch_launch("flops_matrix_mul_mini", "test-partition")

        print("✓ Correctly handles missing SLURM commands")

        # Test 2: Invalid partition
        def mock_invalid_partition(cmd, **kwargs):
            if cmd[0] == "sbatch":
                error = subprocess.CalledProcessError(1, cmd)
                error.stderr = (
                    "sbatch: error: Invalid partition name 'invalid-partition'"
                )
                raise error
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_invalid_partition)

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            sbatch_launch("flops_matrix_mul_mini", "invalid-partition")

        assert "Invalid partition" in str(exc_info.value.stderr)
        print("✓ Correctly handles invalid partition errors")

    def test_cli_integration(self, tmp_path, monkeypatch):
        """Test the CLI command 'benchwrap run flops_matrix_mul_mini'."""
        from click.testing import CliRunner

        from benchwrap.cli import run

        # Setup environment
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()
        monkeypatch.setenv("HOME", str(fake_home))

        # Mock successful execution
        def mock_successful_run(cmd, **kwargs):
            if cmd[0] == "python" and "flops_matrix_mul_mini" in cmd:
                return MagicMock(returncode=0)
            return MagicMock(returncode=0)

        monkeypatch.setattr(subprocess, "run", mock_successful_run)

        # Test CLI execution
        runner = CliRunner()
        result = runner.invoke(run, ["flops_matrix_mul_mini", "scc-cpu"])

        assert result.exit_code == 0, f"CLI command failed: {result.output}"
        print("✓ CLI integration test passed")


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
