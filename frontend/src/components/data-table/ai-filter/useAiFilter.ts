/* Copyright 2026 Marimo. All rights reserved. */

import type { FilterAST, FilterSchema } from "better-filter-bar";
import { parseQuery, resolveRelativeDates } from "better-filter-bar";
import { useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { useRuntimeManager } from "@/core/runtime/config";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import type { FilterGroupType } from "@/plugins/impl/data-frames/schema";
import { Logger } from "@/utils/Logger";
import type { FieldTypesWithExternalType } from "../types";
import { buildAiFilterPrompt } from "./prompt";
import { requestAiFilterQuery } from "./request";
import { fieldTypesToFilterSchema } from "./schema";
import { filterBarAstToMarimo } from "./serialize";

export interface AiFilterState {
  schema: FilterSchema;
  /** FQL text from the last generation; seeds the editor. */
  rawQuery: string;
  /** FQL text currently applied to the table; used for dirty-tracking. */
  appliedRaw: string;
  isActive: boolean;
  isGenerating: boolean;
  error: string | null;
  filterGroup: FilterGroupType | null;
  query: string;
  /** Bumped per generation to re-key (remount) the editor. */
  generationId: number;
  generate: (naturalLanguage: string) => Promise<void>;
  applyFromEditor: (ast: FilterAST, raw: string) => void;
  clear: () => void;
}

/**
 * Drives the "Search with AI" flow: prompts the LLM, then serializes the
 * generated (and edited) FQL into marimo's filter format. Applied on generation
 * and on submit (Enter), never on every keystroke.
 */
export function useAiFilter(
  fieldTypes: FieldTypesWithExternalType | null | undefined,
): AiFilterState {
  const runtimeManager = useRuntimeManager();
  const memoizedFieldTypes = useDeepCompareMemoize(fieldTypes ?? []);
  const schema = useMemo(
    () => fieldTypesToFilterSchema(memoizedFieldTypes),
    [memoizedFieldTypes],
  );

  const [rawQuery, setRawQuery] = useState("");
  const [appliedRaw, setAppliedRaw] = useState("");
  const [isActive, setIsActive] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filterGroup, setFilterGroup] = useState<FilterGroupType | null>(null);
  const [query, setQuery] = useState("");
  const [generationId, setGenerationId] = useState(0);

  const serializeAndApply = useEvent((ast: FilterAST, raw: string) => {
    try {
      // Resolve relative dates ("today", "-7d") before serializing.
      const resolved = resolveRelativeDates(ast);
      const serialized = filterBarAstToMarimo(resolved, memoizedFieldTypes);
      setFilterGroup(serialized.filters);
      setQuery(serialized.query);
      setAppliedRaw(raw);
      setError(null);
    } catch (err) {
      Logger.error("AI filter serialization failed", err);
      setError(err instanceof Error ? err.message : String(err));
    }
  });

  const generate = useEvent(async (naturalLanguage: string) => {
    const text = naturalLanguage.trim();
    if (!text) {
      return;
    }
    setIsActive(true);
    setIsGenerating(true);
    setError(null);
    try {
      const prompt = buildAiFilterPrompt(text, memoizedFieldTypes);
      const fql = await requestAiFilterQuery({ prompt, runtimeManager });
      setRawQuery(fql);
      serializeAndApply(parseQuery(fql, schema), fql);
      setGenerationId((id) => id + 1);
    } catch (err) {
      Logger.error("AI filter generation failed", err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsGenerating(false);
    }
  });

  const applyFromEditor = useEvent((ast: FilterAST, raw: string) => {
    serializeAndApply(ast, raw);
  });

  const clear = useEvent(() => {
    setIsActive(false);
    setIsGenerating(false);
    setError(null);
    setRawQuery("");
    setAppliedRaw("");
    setFilterGroup(null);
    setQuery("");
  });

  return {
    schema,
    rawQuery,
    appliedRaw,
    isActive,
    isGenerating,
    error,
    filterGroup,
    query,
    generationId,
    generate,
    applyFromEditor,
    clear,
  };
}
