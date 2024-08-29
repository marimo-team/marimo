# Deploying

You can deploy marimo in three ways:

1. via an **edit server**, which allows you to create and edit notebooks. On
   the CLI, this is launched with `marimo edit`, and is similar to `jupyter
   notebook`.
2. via a **run server**, which allows you serve marimo notebooks as read-only
   web apps. On the CLI, this is launched with `marimo run notebook.py`
3. programmatically, which allows you serve **read-only** marimo apps
   as part of other ASGI applications, for example using FastAPI.

```{admonition} Sharing lightweight notebooks on the web
:class: tip

To share notebooks on the public web, try using [our online playground
](https://marimo.new). Our playground runs entirely in the browser -- no
backend required, via [WASM](/guides/wasm.md).

Or, to share notebooks with email-based authorization, you can also
try our free [community cloud](https://marimo.io/sign-up), which is
also powered by WASM.

WASM notebooks support most but not all Python features and packages.
```

## Deploying an edit server

Here are a few ways to deploy an edit server on a remote instance:

1. With [ssh-port forwarding](/faq.md#faq-remote), using `marimo edit --headless`.
2. Via docker and our [prebuilt containers](/guides/prebuilt_containers.md).
3. Via a deployment service [such as Railway](/guides/deploying/deploying_railway.md).
4. [Behind JupyterHub](/faq.md#faq-jupyter-hub).

## Deploying as read-only apps

These guides help you deploy marimo notebooks as read-only apps.

|                                 |                                                          |
| :------------------------------ | :------------------------------------------------------- |
| {doc}`programmatically`         | Programmatically run and customize read-only marimo apps |
| {doc}`deploying_docker`         | Deploy with Docker                                       |
| {doc}`authentication`           | Authentication and security                              |
| {doc}`deploying_public_gallery` | Deploy to our public gallery                             |
| {doc}`deploying_marimo_cloud`   | Deploy to Marimo Cloud                                   |
| {doc}`deploying_ploomber`       | Deploy to Ploomber Cloud                                 |

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
