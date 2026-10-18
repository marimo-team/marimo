# marimo + openapi

The frontend of marimo communicates with the backend through an OpenAPI specification, which can be found in [`packages/openapi/api.yaml`](/packages/openapi/api.yaml).

The host protocol has a separate, schema-first contract in
[`protocols/host/openapi.yaml`](/protocols/host/openapi.yaml). Its ownership,
generation commands, and portable conformance checks are documented in
[`protocols/host/README.md`](/protocols/host/README.md).

## Printing the OpenAPI schema

```bash
marimo development openapi
```

## Writing a new OpenAPI schema

The frontend contract is declared in
[`schema.py`](/marimo/_cli/development/schema.py). Add request/response models
or standalone frontend types to `roots`. Types referenced by those roots are
included automatically.

Use `named_exports` to give a union or literal type a schema name. The generator
exports `ClientCommand`, `NotificationMessage`, `MarimoError`, and `DataType`
this way. Add client commands to `ClientCommand`, rather than exporting
individual commands as additional roots.

`KnownUnions` is deprecated but remains for existing downstream consumers.
New consumers should use the named schemas directly, such as
`schemas["ClientCommand"]`.

Regenerate the schema and TypeScript together with Python 3.12:

```bash
make fe-codegen
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
