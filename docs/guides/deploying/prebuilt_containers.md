# Prebuilt containers

marimo provides prebuilt containers for running a marimo server.

You can find the containers and tags on [marimo's GitHub packages page](https://github.com/marimo-team/marimo/pkgs/container/marimo).

We provide the following variants:

- `marimo:latest` - The latest version of marimo
- `marimo:latest-data` - The latest version of marimo with `altair`, `pandas`, and `numpy` preinstalled.
- `marimo:latest-sql` - The latest version of marimo with `marimo[sql]` and `duckdb` preinstalled.

or any particular version of marimo; for example, `marimo:0.8.3`, `marimo:0.8.3-data`, `marimo:0.8.3-sql`.

## Running locally

To run the container locally, you can use the following command:

```bash
docker run -p 8080:8080 -it ghcr.io/marimo-team/marimo:latest-sql
```
