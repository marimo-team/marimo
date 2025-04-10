# Docker Images

This directory contains the Dockerfile for building marimo Docker images.

## Available Images

- `marimo-slim`: Minimal image with just marimo installed
- `marimo-data`: Includes marimo plus data science packages (pandas, numpy, altair) and marimo[recommended,lsp]
- `marimo-sql`: Extends the data image with SQL support (marimo[recommended,lsp,sql])

## Testing locally

To build all images, from the root

```bash
# Build your image, and tag it as my_app
docker build -t my_app . -f docker/Dockerfile

# Start your container, mapping port 8080
docker run -p 8080:8080 -it my_app

# Visit http://localhost:8080
```
