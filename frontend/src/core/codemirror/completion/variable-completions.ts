/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { Variable, Variables } from "@/core/variables/types";

/**
 * Gets completions for variables defined in the notebook.
 */
export function getVariableCompletions(
  variables: Variables,
  skipVariables: Set<string>,
  boost = 3,
  prefix = "",
): Completion[] {
  return Object.values(variables).flatMap<Completion>((variable) => {
    if (skipVariables.has(variable.name)) {
      return [];
    }
    return {
      label: `${prefix}${variable.name}`,
      displayLabel: variable.name,
      detail: variable.dataType ?? "",
      boost: boost,
      type: "variable",
      apply: `${prefix}${variable.name}`,
      section: "Variable",
      info: () => {
        return createVariableInfoElement(variable);
      },
    };
  });
}

function createVariableInfoElement(variable: Variable): HTMLElement {
  const infoContainer = document.createElement("div");
  infoContainer.classList.add(
    "mo-cm-tooltip",
    "docs-documentation",
    "min-w-[200px]",
  );
  infoContainer.style.display = "flex";
  infoContainer.style.flexDirection = "column";
  infoContainer.style.gap = ".8rem";
  infoContainer.style.padding = "0.5rem";

  // Variable header
  const header = document.createElement("div");
  header.classList.add("flex", "items-center", "gap-2");

  const nameBadge = document.createElement("span");
  nameBadge.classList.add("font-bold", "text-base");
  nameBadge.textContent = variable.name;
  header.append(nameBadge);

  if (variable.dataType) {
    const typeBadge = document.createElement("span");
    typeBadge.classList.add(
      "text-xs",
      "px-1.5",
      "py-0.5",
      "rounded-full",
      "bg-purple-100",
      "text-purple-800",
      "dark:bg-purple-900",
      "dark:text-purple-200",
    );
    typeBadge.textContent = variable.dataType;
    header.append(typeBadge);
  }

  infoContainer.append(header);

  // Variable value
  if (variable.value) {
    const valueContainer = document.createElement("div");
    valueContainer.classList.add("flex", "flex-col", "gap-1");

    const valueLabel = document.createElement("div");
    valueLabel.classList.add("text-xs", "text-muted-foreground");
    valueLabel.textContent = "Value:";
    valueContainer.append(valueLabel);

    const valueContent = document.createElement("div");
    valueContent.classList.add(
      "text-xs",
      "font-mono",
      "bg-muted",
      "p-2",
      "rounded",
      "overflow-auto",
      "max-h-40",
    );
    valueContent.textContent = variable.value;
    valueContainer.append(valueContent);

    infoContainer.append(valueContainer);
  }

  return infoContainer;
}
