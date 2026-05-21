# LLM Info

This package contains data for the LLM info.

## Data

Models and providers are stored in the `data` directory.

## Adding a New LLM Model

If you want to add a new LLM model or provider, you can do so by editing the YAML files in the `data` directory (`models.yml` or `providers.yml`) and running `pnpm codegen`.

> **Note:**
> To make it easier for users to choose, keep the number of models to a minimum. Focus on including the latest or recommended models from each provider.

## Syncing from `models.dev`

`pnpm sync-models` appends new models from [`models.dev`](https://models.dev/api.json) to `models.yml`. Existing entries are preserved. Run `pnpm codegen` afterwards.

```bash
pnpm sync-models                          # all providers, 10 newest each
pnpm sync-models --provider=anthropic     # one provider
pnpm sync-models -p openai,google -n 5    # multiple providers, 5 each
pnpm sync-models --replace                # destructive rebuild
```
