# Schemas

This directory contains the schemas for the notebook and session.

## How to update the schemas

1. Run `python scripts/generate_schemas.py` to generate the OpenAPI schema.
2. Run `make fe-codegen` to generate the frontend types.

## Schema backwards compatibility

We check for backwards compatibility using a GitHub action: `.github/workflows/test_schemas.yaml`

This will check that the OpenAPI schema is backwards compatible.

## Adding a new schema

1. Add the new schema to the `marimo/_schemas` directory.
2. Run `marimo edit scripts/generate_schemas.py` and add the schema (should be analogous to others).
3. Run `make fe-codegen` to generate the frontend types.
4. Add the new schema GitHub action to `.github/workflows/test_schemas.yaml`
