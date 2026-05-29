---
name: fill-model-descriptions
description: Fill empty `description: ""` fields in `packages/llm-info/data/models.yml` by querying OpenRouter and provider documentation. Use when the user asks to populate model descriptions, enrich the model catalog, or backfill descriptions after running `pnpm sync-models`.
disable-model-invocation: true
---

# Fill Model Descriptions

## Goal

Replace empty `description: ""` strings in `packages/llm-info/data/models.yml` with concise, accurate one-sentence summaries sourced from OpenRouter first, then provider documentation as a fallback.

## Scope and Contract

- **Only modify entries where `description` is the empty string.** Existing non-empty descriptions are human-curated; never overwrite them.
- The file is a top-level YAML map keyed by provider id (`anthropic:`, `openai:`, …). Each provider's value is an array of model entries.
- Do not modify any other field, reorder entries, or change formatting (flow-style arrays like `roles: [chat, edit]`, blank lines between entries, blank line between provider sections).
- This skill requires network access.

## Workflow

1. **Read** `packages/llm-info/data/models.yml`. Parse it with the `yaml` library's `parseDocument` (NOT `parse`) so formatting and comments are preserved on write-back.

2. **Collect** every entry where `description` is the empty string. Track them as `{ provider, model }` pairs.

3. **Source descriptions** in this priority order:

   **a. OpenRouter** — `GET https://openrouter.ai/api/v1/models` (no auth required). Build a lookup keyed by lowercased `id`. For each `{ provider, model }`, try candidates in this order:
   - `${vendor}/${model}` where `vendor` comes from the Vendor Map below.
   - `${vendor}/${model.replaceAll('-', '.')}` (some OR ids use `.` separators, e.g. `claude-3.5-sonnet`).
   - For Bedrock entries with region/alias prefixes (`us.`, `eu.`, `jp.`, `global.`, `anthropic.`, `minimax.`, `mistral.`, `zai.`, `nvidia.`), strip the prefix and retry with the appropriate vendor.
   - For Google entries with `@default` suffix (e.g. `claude-opus-4-7@default`), strip the suffix and try `anthropic/${rest}`.

   **b. Provider docs** — if no OpenRouter hit, search the canonical provider's docs page (anthropic.com/news, platform.openai.com/docs/models, ai.google.dev/gemini-api/docs/models, mistral.ai/news, x.ai/blog, etc.) for the model's one-line summary. Use the `WebSearch` or `WebFetch` tool.

   **c. Skip** — if neither source has a confident answer, leave `description: ""` and record the `{ provider, model }` for the final summary. Empty is better than wrong.

4. **Truncate** each sourced description per the rules in the "Truncation" section.

5. **Write** the YAML back using targeted `Pair` mutations on the parsed `Document`, not text replacement. Reference implementation: `packages/llm-info/src/sync-models.ts` shows how to load a Document, mutate sequence/map nodes, and stringify with `{ lineWidth: 0, flowCollectionPadding: false }` to preserve formatting.

6. **Validate** by running:
   ```bash
   pnpm --filter @marimo-team/llm-info test
   ```
   The `schema.test.ts` test will catch any structural drift.

7. **Report** to the user:
   - How many entries got descriptions.
   - How many were skipped (with the provider/model list).

## Vendor Map

OpenRouter id vendor prefixes for each marimo provider:

| Marimo provider | OpenRouter vendor prefix | Notes |
|---|---|---|
| `anthropic` | `anthropic` | Direct match in most cases |
| `openai` | `openai` | Direct match |
| `google` | `google` | Strip `@default` suffix if present |
| `mistral` | `mistralai` | Note the `ai` suffix |
| `xai` | `x-ai` | Hyphenated |
| `azure` | `openai` | Azure mostly re-exposes OpenAI models |
| `bedrock` | varies | Strip region prefix (`us.`/`eu.`/`jp.`/`global.`) and use the embedded vendor (`anthropic.foo` → `anthropic/foo`) |
| `github` | varies | Ids like `openai/gpt-4.1` carry the vendor; strip the github layer |
| `openrouter` | embedded in id | Ids like `anthropic/claude-opus-4.7-fast` already carry the vendor |
| `wandb` | embedded in id | Ids like `deepseek-ai/DeepSeek-V3.1`; the prefix is the vendor |
| `opencode-go` | rarely on OR | Source from provider docs |
| `ollama` | not on OR | Source from the Ollama model card |

## Truncation

- **One sentence.** Split on `. ` and take the first. Strip trailing whitespace and any markdown formatting (`**`, `_`, backticks).
- **Hard cap at 200 characters.** If the first sentence is longer, cut at the last word boundary before 200 and append `…`.
- **Strip leading articles** for consistency: prefer "Frontier reasoning model optimized for…" over "This is a frontier reasoning model optimized for…".
- **Prefer capability statements over marketing.** If OpenRouter gives "the best model from X" but the provider docs give "optimized for tool use and long-context reasoning", prefer the latter.

## Examples

**Good** (matches the tone of existing hand-curated entries):
- `Latest Opus model, strongest for coding and long-running professional tasks`
- `Most capable Sonnet-class model, with frontier performance across coding, agents, and professional work`
- `Lightweight Gemma model trained by Google, designed to run on a single GPU`
- `Multimodal Mixture-of-Experts model optimized for complex tool use and reasoning`

**Bad** (do not produce these):
- `Claude 3.5 Sonnet delivers better-than-Opus capabilities, faster-than-Sonnet speeds, at the same Sonnet prices. Sonnet is particularly good at coding, vision…` — too long, contains marketing
- `The best model from Anthropic` — vague, no information content
- `An AI model` — useless
- `**Claude 3.5 Sonnet** is a _frontier_ model…` — markdown not stripped

## Quick Reference

- Data file: `packages/llm-info/data/models.yml`
- Schema: `packages/llm-info/src/index.ts` (`AiModel` interface)
- YAML write reference: `packages/llm-info/src/sync-models.ts` (`buildEntryNode`, `addProviderSection`)
- OpenRouter API: `https://openrouter.ai/api/v1/models` (public, no auth)
- Validation: `pnpm --filter @marimo-team/llm-info test`
