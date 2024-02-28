# Deploying

```{eval-rst}
.. toctree::
  :maxdepth: 2
  :hidden:

  deploying_docker
  deploying_public_gallery
```

These guides help you deploy marimo notebooks.

|                                 |                                                           |
| :------------------------------ | :-------------------------------------------------------- |
| {doc}`deploying_docker`         | Deploying marimo notebooks and apps with Docker           |
| {doc}`deploying_public_gallery` | Deploying marimo notebooks and apps to our public gallery |

```{admonition} Sharing notebooks on the public web
:class: tip

To share notebooks on the public web, try using [WASM
notebooks](../../guides/wasm.md), an implementation of marimo that runs
entirely in the browser -- no backend required.

WASM notebooks support most but not all Python features and packages. See our
[guide on WASM notebooks](../../guides/wasm.md) to learn more.
```

## Health and status endpoints

The following endpoints may be useful when deploying your application:

- `/health` - A health check endpoint that returns a 200 status code if the application is running as expected
- `/healthz` - Same as above, just a different name for easier integration with cloud providers
- `/api/status` - A status endpoint that returns a JSON object with the status of the server

## Configuration

If you would like to deploy your application at a subpath, you can set the `--base-url` flag when running your application.

```bash
marimo run app.py --base-url /subpath
```

## Including code in your application

You can include code in your application by using the `--include-code` flag when running your application.

```bash
marimo run app.py --include-code
```
