#!/usr/bin/env bash
#SBATCH --job-name=marimo
#SBATCH --output=marimo-%j.out
#SBATCH --cpus-per-task=4
#SBATCH --mem=16GB
#SBATCH --time=4:00:00

# Runs the marimo editor on a compute node against the *original* notebook
# file. Connect from your laptop with:
#   ssh -L 3000:NODE:3000 you@cluster
uvx marimo edit --sandbox submit_notebook.py --headless --port 3000
