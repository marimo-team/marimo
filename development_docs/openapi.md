# marimo + openapi

## Printing the OpenAPI schema

```bash
marimo development openapi
```

## Writing a new OpenAPI schema

```bash
marimo development openapi > openapi/api.yaml
```

## Validating an OpenAPI schema

```bash
pipx install openapi-spec-validator
marimo development openapi | openapi-spec-validator -
```

## Generating a client from an OpenAPI schema

```bash
make fe-codegen
```

You will then need to reinstall the package in `/frontend`:

```bash
cd frontend
pnpm update @marimo-team/marimo-api
```