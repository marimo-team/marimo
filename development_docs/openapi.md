# marimo + openapi

The frontend of marimo communicates with the backend through an OpenAPI specification, which can be found in [`packages/openapi/api.yaml`](/packages/openapi/api.yaml).

## Printing the OpenAPI schema

```bash
marimo development openapi
```

## Writing a new OpenAPI schema

To modify the schema, add the type under `_generate_server_api_schema` in [`commands.py`](/marimo/_cli/development/commands.py) and run

```bash
marimo development openapi > packages/openapi/api.yaml
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
