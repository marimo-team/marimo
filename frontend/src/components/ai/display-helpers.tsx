/* Copyright 2024 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";

export function getTagColour(role: Role | "thinking"): string {
  switch (role) {
    case "chat":
      return "bg-[var(--purple-3)] text-[var(--purple-11)]";
    case "autocomplete":
      return "bg-[var(--green-3)] text-[var(--green-11)]";
    case "edit":
      return "bg-[var(--blue-3)] text-[var(--blue-11)]";
    case "thinking":
      return "bg-[var(--purple-4)] text-[var(--purple-12)]";
  }
  return "bg-[var(--mauve-3)] text-[var(--mauve-11)]";
}

export function getCurrentRoleTooltip(role: Role): string {
  switch (role) {
    case "chat":
      return "Current model used for chat conversations";
    case "autocomplete":
      return "Current model used for autocomplete autocomplete";
    case "edit":
      return "Current model used for code edits";
    case "rerank":
      return "Current model used for reranking completions";
    case "embed":
      return "Current model used for embedding";
  }
}
