# Deploy with SkyPilot

[SkyPilot](https://skypilot.readthedocs.io/) is an open-source framework that allows you to run workloads on any cloud (AWS, GCP, Azure, Lambda Cloud, and more) with a unified interface. It's particularly well-suited for running marimo notebooks on GPU instances for machine learning and data science workloads.

marimo notebooks work exceptionally well with SkyPilot because they are stored as pure Python scripts and can be run both interactively and as batch jobs. With marimo's built-in `uv` integration, your notebooks are fully reproducible across different environments.

## Interactive Development

For interactive development with marimo on a SkyPilot cluster, you can launch a cluster and connect to it with SSH port forwarding.

### Launch a cluster

First, create a cluster with your desired resources:

```bash
sky launch --gpus V100:1 -c dev
```

### Connect with port forwarding

Connect to the cluster and forward the port that marimo will use:

```bash
ssh -L 8080:localhost:8080 dev
```

### Start marimo

Inside the cluster, install `uv` and start marimo with the `--sandbox` flag for isolated dependencies:

```bash
pip install uv
uvx marimo edit --sandbox demo.py --port 8080 --token-password=supersecret
```

!!! note "Sandboxed environments"
    The `uvx` command runs marimo without installing it in your environment, and the `--sandbox` flag ensures that notebook dependencies are installed in a separate environment. This makes your development fully reproducible and isolated.

You can now access your marimo notebook at `localhost:8080` in your local browser and authenticate with the password you set.

## Running as Batch Jobs

Because marimo notebooks are Python scripts, they can be submitted as managed SkyPilot jobs. This is useful for training models, running experiments, or processing data without needing an interactive session.

### Create a job-compatible notebook

marimo notebooks can accept command-line arguments using `mo.cli_args()`. Here's an example notebook that demonstrates this:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
# ]
# ///

import marimo

__generated_with = "0.18.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    # Parse command-line arguments
    args = mo.cli_args()
    print(f"Running with arguments: {args}")
    return


if __name__ == "__main__":
    app.run()
```

You can test this locally:

```bash
uv run demo.py --hello world --demo works --lr 0.01
```

This will print:

```
{'hello': 'world', 'demo': 'works', 'lr': '0.01'}
```

### Create a SkyPilot job configuration

Create a YAML file to configure your job:

```yaml
# marimo-job.yaml
name: marimo-demo

# Specify resources for this job
resources:
  accelerators: V100:1

# Point to the folder containing your marimo notebook
workdir: .

# Environment variables (e.g., for W&B, HuggingFace)
envs:
  WANDB_API_KEY: ${WANDB_API_KEY}

# Install uv
setup: pip install uv

# Run the notebook with arguments
run: uv run demo.py --hello world --demo works --lr 0.01
```

### Launch the job

Submit the job to SkyPilot:

```bash
sky jobs launch -n marimo-demo marimo-job.yaml
```

SkyPilot will provision cloud resources, run your notebook, and automatically tear down the resources after the job completes (with a configurable idle timeout).

### Monitor job progress

You can monitor your job using:

```bash
# View logs
sky jobs logs marimo-demo

# Check job status
sky jobs queue

# Launch dashboard
sky jobs dashboard
```

## Benefits of marimo + SkyPilot

- **Reproducible**: marimo's `uv` integration ensures consistent dependency management
- **Cost-effective**: SkyPilot finds the cheapest resources across clouds and automatically terminates idle instances
- **Flexible**: Use the same notebook interactively or as a batch job
- **Cloud-agnostic**: Run on any cloud provider without changing your code

## Learn more

- [SkyPilot documentation](https://skypilot.readthedocs.io/)
- [SkyPilot managed jobs guide](https://skypilot.readthedocs.io/en/latest/examples/managed-jobs.html)
- [marimo CLI arguments](../../api/cli_args.md)
