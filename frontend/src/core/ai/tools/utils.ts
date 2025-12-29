/* Copyright 2026 Marimo. All rights reserved. */

import type { ToolDescription } from "./base";

export function formatToolDescription(description: ToolDescription): string {
  let result = description.baseDescription;
  if (description.whenToUse) {
    result += `\n\n## When to use:\n- ${description.whenToUse.join("\n- ")}`;
  }
  if (description.avoidIf) {
    result += `\n\n## Avoid if:\n- ${description.avoidIf.join("\n- ")}`;
  }
  if (description.prerequisites) {
    result += `\n\n## Prerequisites:\n- ${description.prerequisites.join("\n- ")}`;
  }
  if (description.sideEffects) {
    result += `\n\n## Side effects:\n- ${description.sideEffects.join("\n- ")}`;
  }
  if (description.additionalInfo) {
    result += `\n\n## Additional info:\n- ${description.additionalInfo}`;
  }
  return result;
}
