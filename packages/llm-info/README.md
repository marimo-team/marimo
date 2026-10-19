# LLM Info

This package contains data for the LLM info.

## Data

Models and providers are stored in the `data` directory.

## Adding a New LLM Model

If you want to add a new LLM model or provider, you can do so by editing the YAML files in the `data` directory (`models.yml` or `providers.yml`) and running `pnpm codegen`.

> **Note:**
> To make it easier for users to choose, keep the number of models to a minimum. Focus on including the latest or recommended models from each provider.

## Syncing from `models.dev`

`pnpm sync-models` adds the latest models from [`models.dev`](https://models.dev/api.json) to the top of each provider section in `models.yml`. Existing names, descriptions, and roles are preserved. Machine-sourced metadata is refreshed when upstream supplies it: capabilities, input/output types, release dates, pricing, reasoning options, and token limits. Run `pnpm codegen` afterwards.

`google-vertex` maps into the `google` section, so Anthropic models with `@default` ids (e.g. `claude-opus-5@default`) are Vertex-only — note that in their `description` if you keep them.

```bash
pnpm sync-models                          # all providers, 10 newest each
pnpm sync-models --provider=anthropic     # one provider
pnpm sync-models -p openai,google -n 5    # multiple providers, 5 each
pnpm sync-models --metadata-only          # refresh existing metadata, add no models
pnpm sync-models --replace                # destructive rebuild
```

## Model Metadata

Each provider/model entry can include optional `reasoning_options` and `limits`:

```yaml
reasoning_options:
  - type: effort
    values: [low, medium, high, xhigh, max]
limits: {context: 1000000, output: 128000}
```

Reasoning options mirror models.dev: `effort` lists accepted values (including
`null` or `default` when explicitly listed upstream), `toggle` indicates an
on/off control, and `budget_tokens` includes optional `min` and `max` bounds.
A budget minimum of `-1` retains the upstream automatic-budget sentinel.
Token limits are measured in tokens; values are preserved as supplied upstream,
including zero. Omitted metadata is unknown, not an unsupported capability.

Do not copy options between providers or normalize model aliases to enrich
metadata: their endpoints can expose different controls and limits.

Use `--metadata-only` to refresh all machine-sourced metadata in the current catalog without adding models. `--metadata-only`
cannot be combined with `--replace`. When upstream omits a field or no exact
provider/model match exists, existing metadata is preserved.
