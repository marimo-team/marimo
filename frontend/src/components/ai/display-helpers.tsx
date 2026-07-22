/* Copyright 2026 Marimo. All rights reserved. */

import type { Role } from "@marimo-team/llm-info";

export function getTagColour(role: Role | "thinking"): string {
  switch (role) {
    case "chat":
      return "bg-(--purple-3) text-(--purple-11)";
    case "autocomplete":
      return "bg-(--green-3) text-(--green-11)";
    case "edit":
      return "bg-(--blue-3) text-(--blue-11)";
    case "thinking":
      return "bg-(--purple-4) text-(--purple-12)";
  }
  return "bg-(--mauve-3) text-(--mauve-11)";
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
