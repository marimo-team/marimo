/* Copyright 2024 Marimo. All rights reserved. */

import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
} from "@/core/islands/constants";
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

/**
 * Parses marimo island apps from the DOM
 * @param root - Root element to search within (defaults to document)
 */
export function parseMarimoIslandApps(
  root: Document | Element = document,
): MarimoIslandApp[] {
  const embeds = root.querySelectorAll<HTMLElement>(ISLAND_TAG_NAMES.ISLAND);
  if (embeds.length === 0) {
    Logger.warn("No embedded marimo apps found.");
    return [];
  }

  return parseIslandElementsIntoApps(Array.from(embeds));
}

/**
 * Pure function to parse island elements into app structures
 * @param embeds - Array of island HTML elements
 */
export function parseIslandElementsIntoApps(
  embeds: HTMLElement[],
): MarimoIslandApp[] {
  const apps = new Map<string, MarimoIslandApp>();

  for (const embed of embeds) {
    const appId = embed.getAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID);
    if (!appId) {
      Logger.warn("Embedded marimo cell missing data-app-id attribute.");
      continue;
    }

    const cellData = parseIslandElement(embed);
    if (!cellData) {
      Logger.warn(`Embedded marimo app ${appId} missing cell output or code.`);
      continue;
    }

    if (!apps.has(appId)) {
      apps.set(appId, { id: appId, cells: [] });
    }

    const app = apps.get(appId)!;
    const idx = app.cells.length;
    app.cells.push({
      output: cellData.output,
      code: cellData.code,
      idx: idx,
    });

    // Add data-cell-idx attribute to the island element
    embed.setAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX, idx.toString());
  }

  return [...apps.values()];
}

/**
 * Parses a single island element into cell data
 * @param embed - The island HTML element
 * @returns Cell data or null if invalid
 */
export function parseIslandElement(
  embed: HTMLElement,
): { output: string; code: string } | null {
  const cellOutput = embed.querySelector<HTMLElement>(
    ISLAND_TAG_NAMES.CELL_OUTPUT,
  );
  const code = extractIslandCodeFromEmbed(embed);

  if (!cellOutput || !code) {
    return null;
  }

  return {
    output: cellOutput.innerHTML,
    code: code,
  };
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
  const reactive =
    embed.getAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE) === "true";
  // Non-reactive cells are not guaranteed to have code, and should be treated as
  // such.
  if (!reactive) {
    return "";
  }

  const cellCodeElement = embed.querySelector<HTMLElement>(
    ISLAND_TAG_NAMES.CELL_CODE,
  );
  if (cellCodeElement) {
    return parseIslandCode(cellCodeElement.textContent);
  }

  const editorCodeElement = embed.querySelector<HTMLElement>(
    ISLAND_TAG_NAMES.CODE_EDITOR,
  );
  if (editorCodeElement) {
    return parseIslandEditor(
      editorCodeElement.getAttribute("data-initial-value"),
    );
  }

  return "";
}
