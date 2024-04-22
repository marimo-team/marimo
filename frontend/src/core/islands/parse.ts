/* Copyright 2024 Marimo. All rights reserved. */

import { MarimoIslandElement } from "@/core/islands/components/web-components";
import { Logger } from "@/utils/Logger";
import dedent from "string-dedent";

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
}

export function parseMarimoIslandApps(): MarimoIslandApp[] {
  const apps = new Map<string, MarimoIslandApp>();

  const embeds = document.querySelectorAll<HTMLElement>("marimo-island");
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
    const cellCode = embed.querySelector<HTMLElement>(
      MarimoIslandElement.codeTagName,
    );

    if (!cellOutput || !cellCode) {
      Logger.warn(`Embedded marimo app ${id} missing cell output or code.`);
      continue;
    }

    if (!apps.has(id)) {
      apps.set(id, { id, cells: [] });
    }
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const app = apps.get(id)!;
    app.cells.push({
      output: cellOutput.innerHTML,
      code: parseIslandCode(cellCode.textContent),
    });
  }

  return [...apps.values()];
}

export function createMarimoFile(app: MarimoIslandApp): string {
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

        // HACK: This is probably not the best way to check if the code is async
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

export function parseIslandCode(code: string | undefined | null): string {
  if (!code) {
    return "";
  }
  code = decodeURIComponent(code);
  // string-dedent expects the first and last line to be empty / contain only whitespace, so we pad with \n
  return dedent(`\n${code}\n`).trim();
}
