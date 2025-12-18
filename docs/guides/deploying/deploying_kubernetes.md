# Deploy with Kubernetes

The [marimo-operator](https://github.com/marimo-team/marimo-operator) is a
Kubernetes operator that manages marimo notebook deployments. It handles
persistent storage, resource allocation, and lifecycle management for notebooks
running on Kubernetes clusters.

!!! tip "Quick start"
    For the fastest path to running notebooks on Kubernetes, use the `kubectl-marimo` CLI plugin.
    It handles manifest generation, port forwarding, and file synchronization automatically.

## Prerequisites

- Kubernetes cluster (v1.25+)
- `kubectl` configured with cluster access
- Python 3.9+ with `pip` or `uv`
- Cluster admin permissions (for initial operator installation)

## Install the operator

Install the marimo operator on your cluster:

```bash
kubectl apply -f https://raw.githubusercontent.com/marimo-team/marimo-operator/main/deploy/install.yaml
```

Verify the operator is running:

```bash
kubectl get pods -n marimo-operator-system
```

The output should show the operator pod running:

```
NAME                                               READY   STATUS    RESTARTS   AGE
marimo-operator-controller-manager-xxxxx           1/1     Running   0          30s
```

## Quickstart with kubectl-marimo

The `kubectl-marimo` plugin is the recommended way to deploy notebooks from local files.

### Install the plugin

```bash
# With uv (recommended)
uv tool install kubectl-marimo

# Or with pip
pip install kubectl-marimo
```

### Run a notebook

Edit a notebook interactively on the cluster:

```bash
kubectl marimo edit notebook.py
```

This command:

1. Uploads your notebook to the cluster
2. Creates persistent storage for your changes
3. Starts the marimo server
4. Sets up port forwarding to your local machine

When you stop the command (`Ctrl+C`), it syncs changes back to your local file and tears down the pod.

To run a notebook as a read-only application:

```bash
kubectl marimo run notebook.py
```

### Configure resources

Configure your notebook's Kubernetes resources using frontmatter in your notebook file.

**Python notebooks (.py):**

```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["marimo", "pandas", "numpy"]
#
# [tool.marimo.k8s]
# image = "ghcr.io/marimo-team/marimo:latest"
# storage = "5Gi"
# [tool.marimo.k8s.resources]
# requests.cpu = "500m"
# requests.memory = "2Gi"
# limits.cpu = "2"
# limits.memory = "8Gi"
# ///
```

**Markdown notebooks (.md):**

```yaml
---
title: my-analysis
image: ghcr.io/marimo-team/marimo:latest
storage: 5Gi
resources:
  requests:
    cpu: "500m"
    memory: "2Gi"
  limits:
    cpu: "2"
    memory: "8Gi"
---
```

### Configuration fields

| Field | Description | Default |
|-------|-------------|---------|
| `title` | Resource name in Kubernetes | filename |
| `image` | Container image | `ghcr.io/marimo-team/marimo:latest` |
| `port` | Server port | 2718 |
| `storage` | Persistent volume size | none (ephemeral) |
| `resources` | CPU, memory, GPU requests/limits | none |
| `auth` | Set to `"none"` to disable authentication | token auth |
| `env` | Environment variables | none |

### Manage deployments

```bash
# Sync changes back to local file
kubectl marimo sync notebook.py

# Delete deployment
kubectl marimo delete notebook.py

# List active deployments
kubectl marimo status
```

## GPU workloads

Specify GPU resources in your notebook frontmatter:

**Python notebooks:**

```python
# /// script
# [tool.marimo.k8s.resources]
# limits."nvidia.com/gpu" = 1
# ///
```

**Markdown notebooks:**

```yaml
---
resources:
  limits:
    nvidia.com/gpu: 1
---
```

The Kubernetes scheduler will place your notebook on an appropriate GPU node.

## Cloud storage integration

The marimo operator supports mounting cloud storage (S3-compatible buckets, SSHFS, rsync) in your notebooks. See the [operator documentation](https://github.com/marimo-team/marimo-operator) for mount configuration details.

## Deploy with manifests

For advanced users who need fine-grained control, you can create `MarimoNotebook` resources directly.

### Basic manifest

```yaml
apiVersion: marimo.io/v1alpha1
kind: MarimoNotebook
metadata:
  name: my-notebook
spec:
  source: https://github.com/marimo-team/examples.git
  storage:
    size: 1Gi
```

Apply the manifest:

```bash
kubectl apply -f notebook.yaml
```

Check the status:

```bash
kubectl get marimos
```

Port forward to access:

```bash
kubectl port-forward svc/my-notebook 2718:2718
```

### With GPU and sidecars

```yaml
apiVersion: marimo.io/v1alpha1
kind: MarimoNotebook
metadata:
  name: gpu-notebook
spec:
  source: https://github.com/your-org/notebooks.git
  storage:
    size: 5Gi
  resources:
    requests:
      memory: 4Gi
    limits:
      memory: 16Gi
      nvidia.com/gpu: 1
  sidecars:
    - name: ssh
      image: linuxserver/openssh-server:latest
      exposePort: 2222
```

## Clean up

```bash
# Via plugin (syncs changes first)
kubectl marimo delete notebook.py

# Via kubectl (does not sync)
kubectl delete marimo my-notebook
```

!!! warning "Sync before deleting"
    Using `kubectl delete` directly will **not** sync your changes back to your local file. Use `kubectl marimo delete` to automatically sync before deletion.

## Learn more

- [marimo-operator on GitHub](https://github.com/marimo-team/marimo-operator)
- [SkyPilot deployment](./deploying_skypilot.md) - For multi-cloud VM deployment without Kubernetes
- [Docker deployment](./deploying_docker.md) - For container basics
- [Inlining dependencies](../package_management/inlining_dependencies.md) - For reproducible notebooks
