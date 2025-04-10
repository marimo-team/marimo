# Prebuilt containers

marimo provides prebuilt containers for running a marimo server.

You can find the containers and tags on [marimo's GitHub packages page](https://github.com/marimo-team/marimo/pkgs/container/marimo).

We provide the following variants:

- `marimo:latest` - The latest version of marimo
- `marimo:latest-data` - The latest version of marimo with `marimo[recommended,lsp]`, `altair`, `pandas`, and `numpy` preinstalled.
- `marimo:latest-sql` - The latest version of marimo with `marimo[recommended,lsp,sql]` preinstalled.

or any particular version of marimo; for example, `marimo:0.8.3`, `marimo:0.8.3-data`, `marimo:0.8.3-sql`.

Each container is built on `3.13-slim`, but if you'd like to see different configurations, please file an issue or submit a PR!

## Running locally

To run the container locally, you can use the following command:

```bash
docker run -p 8080:8080 -it ghcr.io/marimo-team/marimo:latest-sql
```

## Use in a Dockerfile

To use a prebuilt container in a Dockerfile, you can use the following command:

```dockerfile
FROM ghcr.io/marimo-team/marimo:latest-sql

# Install any additional dependencies here

CMD ["marimo", "edit", "--no-token", "-p", "8080", "--host", "0.0.0.0"]
```
