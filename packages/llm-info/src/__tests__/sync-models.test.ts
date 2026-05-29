/* Copyright 2026 Marimo. All rights reserved. */

import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { parse } from "yaml";
import {
  MAX_COST_INPUT,
  MAX_COST_OUTPUT,
  MAX_MODELS_PER_PROVIDER,
  MODEL_DENYLIST,
  mergeModels,
} from "../sources/merge.ts";
import type { ModelsDevApi } from "../sources/models-dev.ts";
import { syncModels } from "../sync-models.ts";

const FIXTURE_YAML = `# Manually curated section

anthropic:
  - name: Claude Opus 4.5
    model: claude-opus-4-5
    description: A hand-written description.
    roles: [chat, edit]
    capabilities: [thinking, tool_calling]
    input_types: [text, image, pdf]
    output_types: [text]
    release_date: 2025-11-01
`;

const FIXTURE_API: ModelsDevApi = {
  anthropic: {
    id: "anthropic",
    name: "Anthropic",
    models: {
      // Already in FIXTURE_YAML under `anthropic:` — should be preserved.
      "claude-opus-4-5": {
        id: "claude-opus-4-5",
        name: "Claude Opus 4.5 (upstream-name-should-not-overwrite)",
        reasoning: true,
        tool_call: true,
        release_date: "2025-11-01",
        modalities: { input: ["text", "image", "pdf"], output: ["text"] },
      },
      "claude-opus-4-7": {
        id: "claude-opus-4-7",
        name: "Claude Opus 4.7",
        reasoning: true,
        tool_call: true,
        release_date: "2026-04-15",
        modalities: { input: ["text", "image"], output: ["text"] },
        cost: { input: 15, output: 75 },
      },
    },
  },
  openai: {
    id: "openai",
    name: "OpenAI",
    models: {
      "gpt-5-mini": {
        id: "gpt-5-mini",
        name: "GPT-5 Mini",
        reasoning: false,
        tool_call: true,
        release_date: "2025-08-01",
        modalities: { input: ["text"], output: ["text"] },
      },
      // Also exposed via azure below — should appear under both providers.
      "gpt-5.5": {
        id: "gpt-5.5",
        name: "GPT-5.5",
        reasoning: true,
        tool_call: true,
        release_date: "2026-01-15",
        modalities: { input: ["text", "image", "audio"], output: ["text"] },
      },
      // Missing `release_date` — should fall back to the epoch sentinel.
      "text-embedding-3-large": {
        id: "text-embedding-3-large",
        name: "OpenAI Text Embedding 3 Large",
        reasoning: false,
      },
    },
  },
  azure: {
    id: "azure",
    name: "Azure",
    models: {
      "gpt-5.5": {
        id: "gpt-5.5",
        name: "GPT-5.5",
        reasoning: true,
        tool_call: true,
        release_date: "2026-01-15",
      },
    },
  },
  // Should be ignored entirely (provider not in PROVIDER_MAP).
  "302ai": {
    id: "302ai",
    name: "302 AI",
    models: {
      "some-obscure-model": {
        id: "some-obscure-model",
        name: "Some Obscure Model",
      },
    },
  },
};

describe("mergeModels", () => {
  it("preserves existing entries (matched by provider + model id) and adds new ones", () => {
    const existing = { anthropic: [{ model: "claude-opus-4-5" }] };
    const summary = mergeModels(existing, FIXTURE_API);

    expect(summary.preservedCount).toBe(1);
    expect(summary.skippedExisting).toEqual(["anthropic/claude-opus-4-5"]);
    expect(Object.keys(summary.newEntries).sort()).toEqual([
      "anthropic",
      "azure",
      "openai",
    ]);
    expect(summary.newEntries["anthropic"]!.map((e) => e.model)).toEqual([
      "claude-opus-4-7",
    ]);
    expect(summary.newEntries["openai"]!.map((e) => e.model)).toEqual([
      "gpt-5.5",
      "gpt-5-mini",
      "text-embedding-3-large",
    ]);
    expect(summary.newEntries["azure"]!.map((e) => e.model)).toEqual([
      "gpt-5.5",
    ]);
  });

  it("emits the same model under each provider that exposes it", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const inOpenai = summary.newEntries["openai"]!.find(
      (e) => e.model === "gpt-5.5",
    );
    const inAzure = summary.newEntries["azure"]!.find(
      (e) => e.model === "gpt-5.5",
    );
    expect(inOpenai).toBeDefined();
    expect(inAzure).toBeDefined();
  });

  it("populates capabilities from upstream `reasoning`/`tool_call`", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const opus = summary.newEntries["anthropic"]!.find(
      (e) => e.model === "claude-opus-4-7",
    );
    expect(opus!.capabilities).toEqual(["thinking", "tool_calling"]);

    const embed = summary.newEntries["openai"]!.find(
      (e) => e.model === "text-embedding-3-large",
    );
    expect(embed!.capabilities).toEqual([]);
  });

  it("filters input/output modalities to the supported DataType enum", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const opus = summary.newEntries["anthropic"]!.find(
      (e) => e.model === "claude-opus-4-7",
    );
    expect(opus!.input_types).toEqual(["text", "image"]);
    expect(opus!.output_types).toEqual(["text"]);

    // `audio` is upstream but not in `DataType`, so it gets dropped.
    const gpt55 = summary.newEntries["openai"]!.find(
      (e) => e.model === "gpt-5.5",
    );
    expect(gpt55!.input_types).toEqual(["text", "image"]);
  });

  it("normalizes `release_date` to YYYY-MM-DD, falling back to epoch when missing", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const opus = summary.newEntries["anthropic"]!.find(
      (e) => e.model === "claude-opus-4-7",
    );
    expect(opus!.release_date).toBe("2026-04-15");

    const embed = summary.newEntries["openai"]!.find(
      (e) => e.model === "text-embedding-3-large",
    );
    expect(embed!.release_date).toBe("1970-01-01");
  });

  // Regression: `Date.parse` accepts more than `YYYY-MM-DD`. We must
  // canonicalize, otherwise the YAML and the lex-sort in `sortAndTrim` break.
  it("canonicalizes non-YYYY-MM-DD parseable inputs (timestamp, year-only)", () => {
    const fixture: ModelsDevApi = {
      openai: {
        id: "openai",
        name: "OpenAI",
        models: {
          // Bare year — would have left `"2026"` in the YAML otherwise.
          a: {
            id: "a",
            name: "A",
            reasoning: false,
            tool_call: false,
            release_date: "2026",
          },
          // Full ISO timestamp — would have leaked the `T…Z` suffix.
          b: {
            id: "b",
            name: "B",
            reasoning: false,
            tool_call: false,
            release_date: "2026-05-07T12:34:56Z",
          },
          // Garbage — falls back to the epoch sentinel.
          c: {
            id: "c",
            name: "C",
            reasoning: false,
            tool_call: false,
            release_date: "not-a-date",
          },
        },
      },
    };
    const entries = mergeModels({}, fixture).newEntries["openai"]!;
    const byId = Object.fromEntries(entries.map((e) => [e.model, e]));
    expect(byId["a"]!.release_date).toBe("2026-01-01");
    expect(byId["b"]!.release_date).toBe("2026-05-07");
    expect(byId["c"]!.release_date).toBe("1970-01-01");

    // And the sort is now correct — `b` (May 7) ranks above `a` (Jan 1).
    expect(entries.map((e) => e.model)).toEqual(["b", "a", "c"]);
  });

  it("derives `roles: [embed]` for embedding models", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const embedding = summary.newEntries["openai"]!.find(
      (e) => e.model === "text-embedding-3-large",
    );
    expect(embedding!.roles).toEqual(["embed"]);
  });

  it("derives `roles: [chat, edit]` for general chat models", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const chat = summary.newEntries["anthropic"]!.find(
      (e) => e.model === "claude-opus-4-7",
    );
    expect(chat!.roles).toEqual(["chat", "edit"]);
  });

  it("skips models from providers outside the allowlist", () => {
    const summary = mergeModels({}, FIXTURE_API);
    expect(
      (summary.newEntries as Record<string, unknown>)["302ai"],
    ).toBeUndefined();
  });

  it("sorts new entries newest-first within each provider", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const openaiOrder = summary.newEntries["openai"]!.map((e) => e.model);
    expect(openaiOrder).toEqual([
      "gpt-5.5", // 2026-01-15
      "gpt-5-mini", // 2025-08-01
      "text-embedding-3-large", // epoch sentinel
    ]);
  });

  it("caps new entries to the N latest per provider", () => {
    const make = (id: string, date: string) => ({
      id,
      name: id,
      reasoning: false,
      tool_call: false,
      release_date: date,
    });
    const noisy: ModelsDevApi = {
      anthropic: {
        id: "anthropic",
        models: {
          a1: make("a1", "2020-01-01"),
          a2: make("a2", "2021-01-01"),
          a3: make("a3", "2022-01-01"),
          a4: make("a4", "2023-01-01"),
          a5: make("a5", "2024-01-01"),
        },
      },
    };

    const summary = mergeModels({}, noisy, { maxPerProvider: 2 });
    expect(summary.newEntries["anthropic"]!.map((e) => e.model)).toEqual([
      "a5",
      "a4",
    ]);
  });

  it("defaults to 10 per provider when no cap is passed", () => {
    expect(MAX_MODELS_PER_PROVIDER).toBe(10);
  });

  it("dedupes models that appear under multiple mapped providers (google + google-vertex → google)", () => {
    const fixture: ModelsDevApi = {
      google: {
        id: "google",
        name: "Google",
        models: {
          "gemini-3.1-flash-lite": {
            id: "gemini-3.1-flash-lite",
            name: "Gemini 3.1 Flash Lite",
            reasoning: true,
            tool_call: true,
            release_date: "2026-05-07",
          },
        },
      },
      "google-vertex": {
        id: "google-vertex",
        name: "Google Vertex",
        models: {
          // Same model id; must NOT produce a duplicate entry under `google`.
          "gemini-3.1-flash-lite": {
            id: "gemini-3.1-flash-lite",
            name: "Gemini 3.1 Flash Lite (Vertex)",
            reasoning: true,
            tool_call: true,
            release_date: "2026-05-07",
          },
        },
      },
    };

    const summary = mergeModels({}, fixture);
    const ids = summary.newEntries["google"]!.map((e) => e.model);
    expect(ids).toEqual(["gemini-3.1-flash-lite"]);
    expect(summary.newEntries["google"]).toHaveLength(1);
  });

  it("enforces `maxPerProvider` after deduping across mapped providers", () => {
    const make = (id: string, date: string) => ({
      id,
      name: id,
      reasoning: false,
      tool_call: false,
      release_date: date,
    });
    const fixture: ModelsDevApi = {
      google: {
        id: "google",
        name: "Google",
        models: {
          a: make("a", "2026-01-01"),
          b: make("b", "2026-02-01"),
          c: make("c", "2026-03-01"),
        },
      },
      "google-vertex": {
        id: "google-vertex",
        name: "Google Vertex",
        models: {
          // Overlap with `google` (a, b) + one extra unique to vertex (d).
          a: make("a", "2026-01-01"),
          b: make("b", "2026-02-01"),
          d: make("d", "2026-04-01"),
        },
      },
    };

    const summary = mergeModels({}, fixture, { maxPerProvider: 2 });
    expect(summary.newEntries["google"]!.map((e) => e.model)).toEqual([
      "d", // 2026-04-01
      "c", // 2026-03-01
    ]);
  });

  it("forwards `cost` from models.dev when present, and omits it otherwise", () => {
    const summary = mergeModels({}, FIXTURE_API);
    const opus = summary.newEntries["anthropic"]!.find(
      (e) => e.model === "claude-opus-4-7",
    );
    expect(opus!.cost).toEqual({ input: 15, output: 75 });

    const embed = summary.newEntries["openai"]!.find(
      (e) => e.model === "text-embedding-3-large",
    );
    expect(embed!.cost).toBeUndefined();
  });

  // `-n N` means "the N freshest upstream models" — we then drop ids we
  // already have curated, rather than backfilling with the N+1th, N+2th, ...
  // freshest "missing" model. Otherwise the cap drifts toward "always add N
  // entries per run" instead of tracking the upstream frontier.
  it("picks the top-N latest upstream and only appends ones we don't already have", () => {
    const make = (id: string, date: string) => ({
      id,
      name: id,
      reasoning: false,
      tool_call: false,
      release_date: date,
    });
    const fixture: ModelsDevApi = {
      anthropic: {
        id: "anthropic",
        models: {
          a1: make("a1", "2020-01-01"),
          a2: make("a2", "2021-01-01"),
          a3: make("a3", "2022-01-01"),
          a4: make("a4", "2023-01-01"),
          a5: make("a5", "2024-01-01"),
        },
      },
    };

    // Top 2 = {a5, a4}. We already curated a5 → only a4 is added (not a3).
    const partial = mergeModels({ anthropic: [{ model: "a5" }] }, fixture, {
      maxPerProvider: 2,
    });
    expect(partial.newEntries["anthropic"]!.map((e) => e.model)).toEqual([
      "a4",
    ]);
    expect(partial.skippedExisting).toEqual(["anthropic/a5"]);

    // Top 2 = {a5, a4}. Both already curated → nothing is added; we don't
    // dredge up a3.
    const fullyCovered = mergeModels(
      { anthropic: [{ model: "a5" }, { model: "a4" }] },
      fixture,
      { maxPerProvider: 2 },
    );
    expect(fullyCovered.newEntries["anthropic"]).toBeUndefined();
    expect(fullyCovered.skippedExisting.sort()).toEqual([
      "anthropic/a4",
      "anthropic/a5",
    ]);
  });

  describe("cost filter", () => {
    const make = (
      id: string,
      cost: { input?: number; output?: number } | undefined,
    ) => ({
      id,
      name: id,
      reasoning: false,
      tool_call: false,
      release_date: "2026-01-01",
      ...(cost && { cost }),
    });

    it("pins the price ceilings", () => {
      // Tripping these values is a deliberate product decision — bump them
      // here and update the comment on the constants.
      expect(MAX_COST_INPUT).toBe(30);
      expect(MAX_COST_OUTPUT).toBe(100);
    });

    it("drops models priced at or above the input ceiling", () => {
      const fixture: ModelsDevApi = {
        anthropic: {
          id: "anthropic",
          models: {
            "ok-below": make("ok-below", { input: 29, output: 5 }),
            "blocked-at": make("blocked-at", { input: 30, output: 5 }),
            "blocked-above": make("blocked-above", { input: 100, output: 5 }),
          },
        },
      };
      const summary = mergeModels({}, fixture);
      expect(
        summary.newEntries["anthropic"]!.map((e) => e.model).sort(),
      ).toEqual(["ok-below"]);
    });

    it("drops models priced at or above the output ceiling", () => {
      const fixture: ModelsDevApi = {
        anthropic: {
          id: "anthropic",
          models: {
            "ok-below": make("ok-below", { input: 5, output: 99 }),
            "blocked-at": make("blocked-at", { input: 5, output: 100 }),
            "blocked-above": make("blocked-above", { input: 5, output: 500 }),
          },
        },
      };
      const summary = mergeModels({}, fixture);
      expect(
        summary.newEntries["anthropic"]!.map((e) => e.model).sort(),
      ).toEqual(["ok-below"]);
    });

    it("keeps models with no cost data (assume free / unknown, not frontier)", () => {
      const fixture: ModelsDevApi = {
        anthropic: {
          id: "anthropic",
          models: {
            "no-cost": make("no-cost", undefined),
            "partial-cost-input-only": make("partial-cost-input-only", {
              input: 1,
            }),
            "partial-cost-output-only": make("partial-cost-output-only", {
              output: 1,
            }),
          },
        },
      };
      const summary = mergeModels({}, fixture);
      expect(
        summary.newEntries["anthropic"]!.map((e) => e.model).sort(),
      ).toEqual([
        "no-cost",
        "partial-cost-input-only",
        "partial-cost-output-only",
      ]);
    });

    it("filters before the N-latest cap, so expensive models don't burn the quota", () => {
      const fixture: ModelsDevApi = {
        anthropic: {
          id: "anthropic",
          models: {
            // Newest two are frontier-priced and should be filtered out
            // *before* `maxPerProvider` is applied. Without pre-filtering,
            // a cap of 2 would yield zero additions instead of two.
            "newest-expensive": {
              id: "newest-expensive",
              name: "newest-expensive",
              release_date: "2026-05-01",
              cost: { input: 50, output: 200 },
            },
            "second-newest-expensive": {
              id: "second-newest-expensive",
              name: "second-newest-expensive",
              release_date: "2026-04-01",
              cost: { input: 40, output: 150 },
            },
            "third-newest-cheap": {
              id: "third-newest-cheap",
              name: "third-newest-cheap",
              release_date: "2026-03-01",
              cost: { input: 1, output: 5 },
            },
            "fourth-newest-cheap": {
              id: "fourth-newest-cheap",
              name: "fourth-newest-cheap",
              release_date: "2026-02-01",
              cost: { input: 1, output: 5 },
            },
          },
        },
      };
      const summary = mergeModels({}, fixture, { maxPerProvider: 2 });
      expect(summary.newEntries["anthropic"]!.map((e) => e.model)).toEqual([
        "third-newest-cheap",
        "fourth-newest-cheap",
      ]);
    });
  });

  describe("denylist", () => {
    const make = (id: string, date = "2026-01-01") => ({
      id,
      name: id,
      reasoning: false,
      tool_call: false,
      release_date: date,
    });

    it("seeds the denylist with gpt-5.3-codex-spark under openai", () => {
      // Changing this set is a deliberate product decision — when a model is
      // added or removed here, leave a comment next to it explaining why.
      expect(MODEL_DENYLIST["openai"]?.has("gpt-5.3-codex-spark")).toBe(true);
    });

    it("drops upstream models that match the per-provider denylist", () => {
      const fixture: ModelsDevApi = {
        openai: {
          id: "openai",
          name: "OpenAI",
          models: {
            "gpt-5.3-codex-spark": make("gpt-5.3-codex-spark"),
            "gpt-5.3-codex": make("gpt-5.3-codex"),
          },
        },
      };
      const summary = mergeModels({}, fixture);
      expect(summary.newEntries["openai"]!.map((e) => e.model)).toEqual([
        "gpt-5.3-codex",
      ]);
    });

    it("only blocks the id under the listed provider, not everywhere", () => {
      // A made-up `anthropic/gpt-5.3-codex-spark` would still be synced —
      // denylist entries don't leak across providers.
      const fixture: ModelsDevApi = {
        anthropic: {
          id: "anthropic",
          name: "Anthropic",
          models: {
            "gpt-5.3-codex-spark": make("gpt-5.3-codex-spark"),
          },
        },
      };
      const summary = mergeModels({}, fixture);
      expect(summary.newEntries["anthropic"]!.map((e) => e.model)).toEqual([
        "gpt-5.3-codex-spark",
      ]);
    });

    it("filters before the N-latest cap, so denylisted models don't burn the quota", () => {
      const fixture: ModelsDevApi = {
        openai: {
          id: "openai",
          name: "OpenAI",
          models: {
            // Newest is denylisted — without pre-filtering, a cap of 1 would
            // pick this and add zero. With pre-filtering, the cap falls
            // through to `gpt-5.3-codex`.
            "gpt-5.3-codex-spark": make("gpt-5.3-codex-spark", "2026-05-01"),
            "gpt-5.3-codex": make("gpt-5.3-codex", "2026-04-01"),
          },
        },
      };
      const summary = mergeModels({}, fixture, { maxPerProvider: 1 });
      expect(summary.newEntries["openai"]!.map((e) => e.model)).toEqual([
        "gpt-5.3-codex",
      ]);
    });
  });
});

describe("syncModels", () => {
  let tempDir: string;
  let yamlPath: string;

  beforeEach(() => {
    tempDir = mkdtempSync(join(tmpdir(), "llm-info-sync-test-"));
    yamlPath = join(tempDir, "models.yml");
    writeFileSync(yamlPath, FIXTURE_YAML);
  });

  it("prepends new entries to existing provider sections and creates new ones", async () => {
    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });

    expect(result.added).toBe(5);
    expect(result.preserved).toBe(1);

    const onDisk = readFileSync(yamlPath, "utf-8");
    expect(onDisk).toContain("# Manually curated section");
    expect(onDisk).toContain("description: A hand-written description.");
    expect(onDisk).toContain("model: claude-opus-4-7");
    expect(onDisk).toContain("model: gpt-5-mini");
    // Render dates as plain `YYYY-MM-DD`, not ISO timestamps.
    expect(onDisk).toContain("release_date: 2026-04-15");
    expect(onDisk).not.toContain("T00:00:00.000Z");

    const parsed = parse(onDisk);
    expect(Object.keys(parsed).sort()).toEqual([
      "anthropic",
      "azure",
      "openai",
    ]);
    const opus45 = parsed.anthropic.find(
      (m: { model: string }) => m.model === "claude-opus-4-5",
    );
    expect(opus45.description).toBe("A hand-written description.");
    expect(opus45.name).toBe("Claude Opus 4.5");
    expect(parsed.anthropic.map((m: { model: string }) => m.model)).toEqual([
      "claude-opus-4-7",
      "claude-opus-4-5",
    ]);
  });

  it("renders flow-style arrays and a blank line between entries", async () => {
    await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });
    const onDisk = readFileSync(yamlPath, "utf-8");
    // No `providers:` field on entries — the parent key carries that info.
    expect(onDisk).not.toMatch(/^\s+providers:/m);
    // Flow style for `roles`, `capabilities`, etc.
    expect(onDisk).toMatch(/roles: \[chat, edit\]/);
    expect(onDisk).toMatch(/capabilities: \[thinking, tool_calling\]/);
    // Flow-style map for `cost`.
    expect(onDisk).toMatch(/cost: \{ ?input: 15, ?output: 75 ?\}/);
  });

  it("separates provider sections with a blank line", async () => {
    // Fresh bootstrap so we exercise both `renderFresh` and append paths.
    writeFileSync(yamlPath, "");
    await syncModels({ modelsYamlPath: yamlPath, modelsDev: FIXTURE_API });
    const fresh = readFileSync(yamlPath, "utf-8");
    // Every top-level provider key (except the first) is preceded by a blank line.
    expect(fresh).not.toMatch(/^\S.*\n[a-z][a-z0-9-]*:$/m);

    // Re-sync against an upstream that adds a new provider — that section
    // should also be preceded by a blank line when appended. `wandb` is in
    // PROVIDER_MAP but not in FIXTURE_API.
    const extended: ModelsDevApi = {
      ...FIXTURE_API,
      wandb: {
        id: "wandb",
        name: "Weights & Biases",
        models: {
          "deepseek-v3.1": {
            id: "deepseek-v3.1",
            name: "DeepSeek V3.1",
            reasoning: false,
            tool_call: true,
            release_date: "2026-03-01",
          },
        },
      },
    };
    await syncModels({ modelsYamlPath: yamlPath, modelsDev: extended });
    const after = readFileSync(yamlPath, "utf-8");
    expect(after).toMatch(/\n\nwandb:\n/);
  });

  it("is idempotent: running twice produces no further changes", async () => {
    await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });
    const afterFirst = readFileSync(yamlPath, "utf-8");

    const secondResult = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });
    const afterSecond = readFileSync(yamlPath, "utf-8");

    expect(secondResult.added).toBe(0);
    expect(afterSecond).toEqual(afterFirst);
  });

  it("never overwrites a hand-curated entry, even when models.dev disagrees", async () => {
    await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });
    const onDisk = readFileSync(yamlPath, "utf-8");
    expect(onDisk).not.toContain("upstream-name-should-not-overwrite");
    expect(onDisk).toContain("name: Claude Opus 4.5");
  });

  it("`mode: replace` overwrites the file with only auto-synced entries", async () => {
    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
      mode: "replace",
    });

    // `claude-opus-4-5` is no longer treated as existing, so it re-appears.
    expect(result.added).toBe(6);
    expect(result.preserved).toBe(0);

    const onDisk = readFileSync(yamlPath, "utf-8");
    expect(onDisk).not.toContain("# Manually curated section");
    expect(onDisk).not.toContain("A hand-written description.");

    const parsed = parse(onDisk);
    const opus45 = parsed.anthropic.find(
      (m: { model: string }) => m.model === "claude-opus-4-5",
    );
    expect(opus45.description).toBe("");
  });

  it("bootstraps from an empty models.yml", async () => {
    writeFileSync(yamlPath, "");

    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });

    expect(result.added).toBe(6);
    expect(result.preserved).toBe(0);

    const onDisk = readFileSync(yamlPath, "utf-8");
    const parsed = parse(onDisk);
    expect(parsed).toBeTypeOf("object");
    expect(parsed.anthropic).toBeDefined();
    expect(parsed.openai).toBeDefined();
  });

  it("restricts the sync to the requested providers", async () => {
    writeFileSync(yamlPath, "");
    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
      providers: ["anthropic"],
    });

    expect(result.added).toBe(2); // claude-opus-4-5 + claude-opus-4-7
    const parsed = parse(readFileSync(yamlPath, "utf-8"));
    expect(Object.keys(parsed)).toEqual(["anthropic"]);
    expect(
      parsed.anthropic.map((m: { model: string }) => m.model).sort(),
    ).toEqual(["claude-opus-4-5", "claude-opus-4-7"]);
  });

  it("preserves untouched provider sections when filtering", async () => {
    // Start with existing entries under both anthropic and openai; sync only
    // anthropic and confirm openai is left alone.
    const seed = `anthropic:
  - name: Existing Anthropic
    model: claude-existing
    description: hand-curated
    roles: [chat, edit]
    capabilities: []
    input_types: []
    output_types: []
    release_date: 2024-01-01

openai:
  - name: Existing OpenAI
    model: gpt-existing
    description: hand-curated
    roles: [chat, edit]
    capabilities: []
    input_types: []
    output_types: []
    release_date: 2024-01-01
`;
    writeFileSync(yamlPath, seed);

    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
      providers: ["anthropic"],
    });

    // openai entries are not counted as preserved (out of filter scope).
    expect(result.preserved).toBe(1);
    expect(result.added).toBe(2);

    const onDisk = readFileSync(yamlPath, "utf-8");
    expect(onDisk).toContain("model: gpt-existing"); // openai section untouched
    expect(onDisk).not.toContain("model: gpt-5-mini"); // openai sync skipped
    expect(onDisk).toContain("model: claude-opus-4-7"); // anthropic synced
  });

  it("threads `maxPerProvider` through to the merge", async () => {
    writeFileSync(yamlPath, "");
    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
      maxPerProvider: 1,
    });

    // With 1 per provider: anthropic gets 1, openai gets 1, azure gets 1.
    // claude-opus-4-5 (preserved earlier) doesn't apply here since the file
    // starts empty.
    expect(result.added).toBe(3);
    const parsed = parse(readFileSync(yamlPath, "utf-8"));
    expect(parsed.anthropic).toHaveLength(1);
    expect(parsed.openai).toHaveLength(1);
    expect(parsed.azure).toHaveLength(1);
  });

  it("does not write the file when there are no new entries", async () => {
    const full = `anthropic:
  - name: Claude Opus 4.5
    model: claude-opus-4-5
  - name: Claude Opus 4.7
    model: claude-opus-4-7
openai:
  - name: GPT-5 Mini
    model: gpt-5-mini
  - name: GPT-5.5
    model: gpt-5.5
  - name: OpenAI Text Embedding 3 Large
    model: text-embedding-3-large
azure:
  - name: GPT-5.5
    model: gpt-5.5
`;
    writeFileSync(yamlPath, full);
    const before = readFileSync(yamlPath, "utf-8");

    const result = await syncModels({
      modelsYamlPath: yamlPath,
      modelsDev: FIXTURE_API,
    });

    const after = readFileSync(yamlPath, "utf-8");
    expect(result.added).toBe(0);
    expect(after).toEqual(before);
  });
});
