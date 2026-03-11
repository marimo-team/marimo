# Deploy notebook servers or apps

marimo can be deployed as an "edit" server for creating, running, and editing
notebooks, or an app server for serving read-only web apps. For convenience,
you can use our [pre-built containers](prebuilt_containers.md).

!!! tip "Sharing notebooks on the public web"
    To share notebooks on the public web without managing infrastructure, try
    [molab](../molab.md), our free cloud-hosted notebook environment

## Notebook servers

Deploy an edit server (`marimo edit`) to let users create and edit notebooks
on a remote instance.

| Guide | Description |
| ----- | ----------- |
| [JupyterHub](jupyterhub.md) | Run marimo inside JupyterHub with our JupyterLab extension |
| [Kubernetes](deploying_kubernetes.md) | Deploy on Kubernetes |
| [SkyPilot](deploying_skypilot.md) | Deploy on cloud VMs with SkyPilot |
| [Slurm](deploying_slurm.md) | Run on HPC clusters with Slurm |

You can also deploy an edit server with [ssh port forwarding](../../faq.md#faq-remote)
using `marimo edit --headless`.

## Apps

Deploy notebooks as read-only web apps (`marimo run`) or embed them in
other applications.

| Guide | Description |
| ----- | ----------- |
| [FastAPI](programmatically.md) | Programmatically run marimo apps as part of ASGI applications |
| [Authentication](authentication.md) | Authentication and security |
| [Docker](deploying_docker.md) | Deploy with Docker |
| [HuggingFace](deploying_hugging_face.md) | Deploy to Hugging Face Spaces |
| [Railway](deploying_railway.md) | Deploy to Railway |
| [nginx](deploying_nginx.md) | Deploy behind nginx |

### Health and status endpoints

The following endpoints may be useful when deploying your application:

- `/health` - A health check endpoint that returns a 200 status code if the application is running as expected
- `/healthz` - Same as above, just a different name for easier integration with cloud providers
- `/api/status` - A status endpoint that returns a JSON object with the status of the server

### Configuration

If you would like to deploy your application at a subpath, you can set the `--base-url` flag when running your application.

```bash
marimo run app.py --base-url /subpath
```

### Including code in your application

You can include code in your application by using the `--include-code` flag when running your application.

```bash
marimo run app.py --include-code
```
