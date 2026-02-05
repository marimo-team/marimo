/* Copyright 2026 Marimo. All rights reserved. */

import { MarimoIslandElement } from "@/core/islands/components/web-components";
import { Logger } from "@/utils/Logger";

/**
 * DOM elements look like this:
 * <marimo-island data-app-id="{self._app_id}">
 *   <marimo-cell-output>
 *     <div> Hello, world! </div>
 *   </marimo-cell-output>
 *   <marimo-cell-code>
 *     encoded(print("Hello, world!"))
 *   </marimo-cell-code>
 * </marimo-island>
 */

export interface MarimoIslandApp {
  /**
   * ID since we allow multiple apps on the same page.
   */
  id: string;
  /**
   * Cells in the app.
   */
  cells: MarimoIslandCell[];
}

interface MarimoIslandCell {
  /**
   * Output of the cell.
   */
  output: string;
  /**
   * Code of the cell.
   */
  code: string;
  /**
   * Index of the cell.
   */
  idx: number;
}

export function parseMarimoIslandApps(): MarimoIslandApp[] {
  const apps = new Map<string, MarimoIslandApp>();

  const embeds = document.querySelectorAll<HTMLElement>(
    MarimoIslandElement.tagName,
  );
  if (embeds.length === 0) {
    Logger.warn("No embedded marimo apps found.");
    return [];
  }

  for (const embed of embeds) {
    const id = embed.dataset.appId;
    if (!id) {
      Logger.warn("Embedded marimo cell missing data-app-id attribute.");
      continue;
    }

    const cellOutput = embed.querySelector<HTMLElement>(
      MarimoIslandElement.outputTagName,
    );
    const code = extractIslandCodeFromEmbed(embed);

    if (!cellOutput || !code) {
      Logger.warn(`Embedded marimo app ${id} missing cell output or code.`);
      continue;
    }

    if (!apps.has(id)) {
      apps.set(id, { id, cells: [] });
    }
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const app = apps.get(id)!;
    const idx = app.cells.length;
    app.cells.push({
      output: cellOutput.innerHTML,
      code: code,
      idx: idx,
    });

    // Add data-cell-idx attribute to the island element
    embed.dataset.cellIdx = idx.toString();
  }

  return [...apps.values()];
}

export function createMarimoFile(app: { cells: { code: string }[] }): string {
  const lines = [
    "import marimo",
    "app = marimo.App()",
    app.cells
      .map((cell) => {
        // Add 4 spaces to each line
        const code = cell.code
          .split("\n")
          .map((line) => `    ${line}`)
          .join("\n");

        // TODO: Handle async cells better
        // This is probably not the best way to check if the code is async
        // Ideally this is pushed into the Python code
        const isAsync = code.includes("await ");
        const prefix = isAsync ? "async def" : "def";

        // Wrap in a function
        return `@app.cell\n${prefix} __():\n${code}\n    return`;
      })
      .join("\n"),
  ];

  return lines.join("\n");
}

export function parseIslandEditor(code: string | undefined | null): string {
  if (!code) {
    return "";
  }
  try {
    return `${JSON.parse(code)}`;
  } catch {
    return code;
  }
}

export function parseIslandCode(code: string | undefined | null): string {
  if (!code) {
    return "";
  }
  return decodeURIComponent(code).trim();
}

export function extractIslandCodeFromEmbed(embed: HTMLElement): string {
  const reactive = embed.dataset.reactive === "true";
  // Non-reactive cells are not guaranteed to have code, and should be treated as
  // such.
  if (!reactive) {
    return "";
  }

  const cellCodeElement = embed.querySelector<HTMLElement>(
    MarimoIslandElement.codeTagName,
  );
  if (cellCodeElement) {
    return parseIslandCode(cellCodeElement.textContent);
  }

  const editorCodeElement = embed.querySelector<HTMLElement>(
    MarimoIslandElement.editorTagName,
  );
  if (editorCodeElement) {
    return parseIslandEditor(editorCodeElement.dataset.initialValue);
  }

  return "";
}
