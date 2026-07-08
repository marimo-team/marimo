/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldTypesWithExternalType } from "../types";
import { dataTypeToFieldType } from "./schema";

/** The better-filter-bar (FQL) grammar, shown to the model as a spec. */
export const AI_FILTER_SYNTAX = `status:open                          # exact match
status:(open,closed)                 # multi-value (OR within list)
status:open author:alice             # implicit AND
status:open AND author:alice         # explicit AND
status:open OR status:closed         # OR
NOT status:closed                    # negation
priority>=2                          # comparison (=, !=, >, >=, <, <=)
created:>2024-01-01                  # date comparison
label:"needs review"                 # quoted value (required for spaces)
(status:open OR status:draft) AND priority>=3  # grouping`;

/**
 * Build the LLM prompt: schema + FQL grammar + the request. Deliberately
 * directive because the completion endpoint wraps it in a code-gen system prompt.
 */
export function buildAiFilterPrompt(
  naturalLanguage: string,
  fieldTypes: FieldTypesWithExternalType | null | undefined,
): string {
  const columns = (fieldTypes ?? [])
    .map(([name, [dataType]]) => `- ${name}: ${dataTypeToFieldType(dataType)}`)
    .join("\n");

  return [
    "You translate a natural-language request into a single-line filter query for a data table.",
    "",
    "## Available columns (name: type)",
    columns || "(no columns)",
    "",
    "## Filter query grammar",
    AI_FILTER_SYNTAX,
    "",
    "## Rules",
    "- Only reference columns from the list above, using their exact names.",
    "- Use `field:value` for text and boolean columns; use comparisons (>, >=, <, <=, =, !=) only for number and date columns.",
    '- Quote values that contain spaces: field:"two words".',
    "- Combine conditions with AND / OR / NOT and parentheses as needed.",
    "- Respond with ONLY the filter query on a single line. No explanation, no code fences, no trailing punctuation.",
    "",
    "## Request",
    naturalLanguage,
  ].join("\n");
}
