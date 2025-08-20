import importlib.resources as res
import os
import pathlib
import stat
import subprocess
import time

import h5py
import pandas as pd


def run_slurm_job(bench_name: str, partition: str, nodes: int = 1):
    """
    Runs a SLURM job for the specified benchmark name, partition, and number of nodes.
    The function submits a job using the `sbatch` command and handles potential errors
    encountered during the job submission process. It also logs the job submission status.

    Args:
        bench_name (str): The name of the benchmark to run.
        partition (str): The SLURM partition where the job should be executed. Can be an
            empty string if no partition is provided.
        nodes (int): The number of nodes required for the job.

    Raises:
        subprocess.CalledProcessError: If there is an error in the `sbatch` command
            execution, this exception will be raised with the relevant stderr output.
    """
    try:
        if partition is None:
            partition = ""
            print("Running No Partition provided")

        job_id = sbatch_launch(bench_name, partition, nodes)
    except subprocess.CalledProcessError as e:
        print("sbatch stderr:\n", e.stderr, "\n---")
        raise

    if partition == "":
        print("Job n:", job_id, "submitted ...")  #
    else:
        print(f"Job n: {job_id} submitted at partition: {partition} ...")


def h5_analysis(job_id: str):
    post_cmd = "sh5util -j"

    print("Job finished. Generating HDF5 output...")
    subprocess.run(post_cmd.split() + [str(job_id)], check=True, capture_output=True)

    result_file = f"job_{job_id}.h5"
    while not os.path.exists(result_file):
        time.sleep(5)

    read_h5(result_file)

    sacct_cmd = f"sacct --format=jobid,elapsed,AveCPUFreq,ConsumedEnergy,ConsumedEnergyRaw -P -j {job_id}"
    result2 = subprocess.run(sacct_cmd.split(), check=True, capture_output=True)
    print(result2.stdout.decode("utf-8"))


def h5tree(filename, file, prefix=""):
    """
    Recursively prints the hierarchy of an HDF5 file and reads any datasets.

    Parameters:
        filename (str): The path to the HDF5 file (used by pandas).
        file (h5py.File or h5py.Group or h5py.Dataset): Current node in HDF5 tree.
        prefix (str): Visual indentation for printing tree structure (used recursively).

    Behavior:
        - If a group, it prints its keys and recurses into children.
        - If a dataset, it reads and prints it using pandas.
    """
    print(prefix + file.name)
    if isinstance(file, h5py._hl.group.Group):
        print(file.keys())
        for key in file.keys():
            h5tree(filename, file[key], prefix=prefix + " ")
    elif isinstance(file, h5py._hl.dataset.Dataset):
        df = pd.read_hdf(filename, file.name)
        print(df)


def read_h5(filename):
    """
    Opens an HDF5 file and prints its full structure and contents using h5tree().

    Parameters:
        filename (str): Path to the HDF5 file.

    Behavior:
        - Opens the file using h5py.
        - Delegates the recursive inspection to `h5tree()`.
    """
    with h5py.File(filename, "r") as f:
        h5tree(filename, f)


def _make_executable(p: pathlib.Path) -> None:
    "Ensure the file has u+x so Slurm can read it."
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def sbatch_launch(bench_name: str, partition: str = "scc-cpu", nodes: int = 1) -> int:
    """
    Launches a benchmarking script on a SLURM cluster using the `sbatch` command. The function configures
    the SLURM batch job submission command with job-specific parameters including the benchmarking script,
    partition type, and number of nodes.
    Parameters:
        bench_name: str
            The name of the benchmark to be executed. This corresponds to a script available within
            the benchmarking resources.
        partition: str, optional
            The partition on the SLURM cluster to use for the job. Defaults to "scc-cpu".
        nodes: int, optional
            The number of computing nodes required for the job. Defaults to 1.

    Returns:
        int
            The SLURM job ID of the submitted job.

    Raises:
        Various exceptions are raised depending on the specific subprocess execution or filesystem operations.
    """
    #Cmd definition
    script_res = res.files("benchwrap.benchmarks") / bench_name / "job_start.sh"
    os.makedirs(
            f"{os.environ['HOME']}/.local/share/benchwrap/jobs",
            exist_ok=True,
    )

    with res.as_file(script_res) as script_path:
        _make_executable(script_path)

        cmd = ["sbatch", "--parsable", "--hold"]

        # Partition
        if partition:
            cmd += [f"--partition={partition}"]

        # N of nodes
        cmd += [f"--nodes={nodes}"]

        #Job name
        cmd += [f"--job-name={bench_name}"]

        # Output and Error
        cmd += [
            "--output",
            f"{os.environ['HOME']}/.local/share/benchwrap/jobs/job_%j/slurm-%j.out",
            "--error",
            f"{os.environ['HOME']}/.local/share/benchwrap/jobs/job_%j/slurm-%j.err",
            str(script_path),
        ]

        try:
            completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print("STDERR:", e.stderr)
            raise

        job_id = int(completed.stdout.strip().split(";")[0])
        os.makedirs(
            f"{os.environ['HOME']}/.local/share/benchwrap/jobs/job_{job_id}",
            exist_ok=True,
        )
        subprocess.run(["scontrol", "release", str(job_id)], check=True)
        return job_id


def check_ior():
    if os.path.exists(
        f"{os.environ["HOME"]}/.local/share/benchwrap/benchmarks/io500/bin/ior"
    ):
        return True
    else:
        print("No ior found")
        return False


def check_io500():
    if os.path.exists(f"{os.environ["HOME"]}/.local/share/benchwrap/benchmarks/io500"):
        return True
    else:
        print("No io500 found")
        return False


def get_ior():

    assert check_mpi() == True
    print("Compiling ior")
    os.chdir(f"{os.environ['HOME']}/.local/share/benchwrap/benchmarks/io500")
    subprocess.run(["bash", "prepare.sh"])


def get_io500():
    os.chdir(f"{os.environ['HOME']}/.local/share/benchwrap/benchmarks")
    subprocess.run(["git", "clone", "https://github.com/IO500/io500.git"])


def check_mpi():
    try:
        subprocess.run(["mpirun", "--version"], check=True, capture_output=True)
        return True
    except FileNotFoundError:
        print("MPI compiler not installed")
        return False
    except subprocess.CalledProcessError:
        print("MPI compiler present but not functional")
        return False
