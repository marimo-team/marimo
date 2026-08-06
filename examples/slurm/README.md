# Slurm examples

Working examples for running marimo notebooks on Slurm-managed clusters,
including Slurm-on-Kubernetes setups like SUNK. See the
[Slurm deployment guide](https://docs.marimo.io/guides/deploying/deploying_slurm/)
for the full walkthrough.

Both patterns require [uv](https://docs.astral.sh/uv/getting-started/installation/)
on `PATH` (Slurm propagates the submission shell's environment to the job by
default).

## Interactive: marimo editor on a compute node

[`run_marimo.sh`](run_marimo.sh) opens
[`submit_notebook.py`](submit_notebook.py); swap in your own notebook path
to edit something else.

```bash
sbatch run_marimo.sh
squeue -u $USER                      # find the compute node
ssh -L 3000:NODE:3000 you@cluster    # tunnel from your laptop
# open http://localhost:3000
```

## Batch: a notebook that is its own Slurm job

[`submit_notebook.py`](submit_notebook.py) is simultaneously a marimo
notebook, a Python script, and an sbatch submission — the `#SBATCH`
directives, the dependencies (PEP 723), and the code travel in one file:

```bash
chmod +x submit_notebook.py
sbatch submit_notebook.py --n 500000
```

The `--script` flag in the shebang lets `uv` run Slurm's spooled,
extensionless copy of the file.

Tips for shared clusters:

- `uv`'s wheel cache lives in `~/.cache/uv`; point `UV_CACHE_DIR` at a shared
  or project filesystem so compute nodes reuse downloads.
- If your home and cache live on different mounts, set `UV_LINK_MODE=copy`.
- `mo.persistent_cache` writes to `__marimo__/cache/` next to the notebook,
  or under the job's working directory when the notebook's directory is not
  writable (as with Slurm's spooled batch copies) — on a shared filesystem
  the cache outlives the job, so resubmissions skip completed work.
