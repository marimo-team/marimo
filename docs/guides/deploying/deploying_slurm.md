# Deploy on Slurm/HPC Clusters

This guide shows how to run marimo notebooks on Slurm-managed clusters, including traditional HPC systems and Slurm-on-Kubernetes setups like [SUNK](https://docs.coreweave.com/docs/products/sunk) (CoreWeave).

Since marimo notebooks are pure Python scripts, it's easy to submit as Slurm jobs for both interactive development and batch processing.

## Interactive Development

For interactive development, submit a job that runs `marimo edit` and connect via SSH port forwarding.

### Submit the job

Create a script (`run_marimo.sh`):

```bash
#!/bin/bash
#SBATCH --job-name=marimo
#SBATCH --output=marimo-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB
#SBATCH --time=4:00:00

# module load or otherwise set up environment

python -m marimo edit notebook.py --headless --port 3000
```

Submit it:

```bash
sbatch run_marimo.sh
```

### Connect with port forwarding

Once the job is running, find the compute node and create an SSH tunnel:

```bash
# Find which node your job is running on
squeue -u $USER -o "%.18i %.9P %.8j %.8u %.2t %.10M %.6D %R"

# Create tunnel (replace NODE with actual node name)
ssh -L 3000:NODE:3000 username@cluster.edu
```

Open `http://localhost:3000` in your browser.

## Running as Batch Jobs

Because marimo notebooks are just Python scripts, they can readily be run as
batch jobs. This simple example uses [`mo.cli_args()`][marimo.cli_args] to pass
parameters:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    args = mo.cli_args()
    print(f"Running with: {args}")
    return


if __name__ == "__main__":
    app.run()
```

Submit as a job:

```bash
#!/bin/bash
#SBATCH --job-name=marimo-job
#SBATCH --output=marimo-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB

python notebook.py --learning-rate 0.01 --epochs 100
```

### Using GPUs

Add GPU resources to your SBATCH directives:

/// tab | Interactive development
```bash
#!/bin/bash
#SBATCH --job-name=marimo
#SBATCH --output=marimo-%j.out
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB
#SBATCH --time=4:00:00

# module load or otherwise set up environment

python -m marimo edit notebook.py --headless --port 3000
```

/// 

/// tab | Batch jobs

```bash
#!/bin/bash
#SBATCH --job-name=marimo-gpu
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32GB

python notebook.py
```

///

## Inlining configuration in notebook files

You can inline SBATCH directives in your notebook file. If used alongside marimo's support for
[inlining package dependencies](../package_management/inlining_dependencies.md) ("sandboxing"),
this lets you create fully self-contained notebooks.

/// tab | Interactive development

```python
#!/usr/bin/env -S python -m marimo edit --sandbox
#SBATCH --job-name=marimo-job
#SBATCH --output=marimo-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    print("Hello World!")
    return


if __name__ == "__main__":
    app.run()
```

/// tab | Batch job

```
#!/usr/bin/env -S python
#SBATCH --job-name=marimo-job
#SBATCH --output=marimo-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

app = marimo.App()


@app.cell
def _():
    import marimo as mo
    print("Hello World!")
    return


if __name__ == "__main__":
    app.run()
```

///


Make executable and submit directly:

```bash
chmod +x notebook.py
sbatch notebook.py
```

Sandboxing requires [uv](https://docs.astral.sh/uv/getting-started/installation/) to be installed.

## Learn more

- [Slurm examples](https://github.com/marimo-team/marimo/tree/main/examples/slurm) - Complete working examples
- [Slurm documentation](https://slurm.schedmd.com/documentation.html)
- [SUNK (Slurm on Kubernetes)](https://docs.coreweave.com/docs/products/sunk)
- [marimo CLI arguments](../../api/cli_args.md)
