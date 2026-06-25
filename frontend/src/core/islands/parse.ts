/* Copyright 2026 Marimo. All rights reserved. */

import {
  ISLAND_DATA_ATTRIBUTES,
  ISLAND_TAG_NAMES,
  ISLANDS_JSON_SCRIPT_TYPE,
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
   * Whether cells came from a supported JSON payload instead of DOM parsing.
   */
  payloadBacked?: boolean;
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
  /**
   * Stable cell identifier, when provided by the island payload.
   */
  cellId?: string;
  /**
   * Whether the generated marimo cell should be present but not executed.
   */
  disabled?: boolean;
}

interface MarimoIslandPayload {
  schemaVersion: 1;
  appId: string;
  cells: MarimoIslandPayloadCell[];
}

interface MarimoIslandPayloadCell {
  cellId: string;
  code: string;
  outputHtml: string;
  reactive: boolean;
  displayCode: boolean;
  displayOutput: boolean;
}

/**
 * Parses marimo island apps from the DOM
 * @param root - Root element to search within (defaults to document)
 */
export function parseMarimoIslandApps(
  root: Document | Element = document,
): MarimoIslandApp[] {
  const embeds = [
    ...root.querySelectorAll<HTMLElement>(ISLAND_TAG_NAMES.ISLAND),
  ];
  const payloads = parseMarimoIslandPayloads(root);
  if (embeds.length === 0 && payloads.length === 0) {
    Logger.warn("No embedded marimo apps found.");
    return [];
  }

  if (payloads.length > 0) {
    return parsePayloadBackedApps(embeds, payloads);
  }

  return parseIslandElementsIntoApps(embeds);
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

    // Non-reactive islands are static — they don't participate in the kernel
    const reactive =
      embed.getAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE) === "true";
    if (!reactive) {
      continue;
    }

    const cellData = parseIslandElement(embed);
    if (!cellData) {
      Logger.warn(`Embedded marimo app ${appId} missing cell output or code.`);
      continue;
    }

    let app = apps.get(appId);
    if (!app) {
      app = { id: appId, cells: [] };
      apps.set(appId, app);
    }

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

function parsePayloadBackedApps(
  embeds: HTMLElement[],
  payloads: MarimoIslandPayload[],
): MarimoIslandApp[] {
  const apps = new Map<string, MarimoIslandApp>();
  const matchedPayloadCells = new Map<MarimoIslandPayloadCell, HTMLElement>();
  const consumedEmbeds = new Set<HTMLElement>();
  const acceptedPayloads: MarimoIslandPayload[] = [];

  for (const payload of payloads) {
    let hasMatchedIsland = false;
    for (const cell of payload.cells) {
      const embed = findMatchingIsland({
        embeds,
        appId: payload.appId,
        cell,
        consumedEmbeds,
      });
      if (!embed) {
        continue;
      }
      consumedEmbeds.add(embed);
      matchedPayloadCells.set(cell, embed);
      materializeIslandPayload(embed, cell);
      hasMatchedIsland = true;
    }
    // Only payloads matched to island anchors can start runtime apps.
    if (hasMatchedIsland) {
      acceptedPayloads.push(payload);
    }
  }

  const payloadAppIds = new Set(
    acceptedPayloads.map((payload) => payload.appId),
  );
  const reactivePayloadAppIds = new Set(
    acceptedPayloads
      .filter((payload) => payload.cells.some((cell) => cell.reactive))
      .map((payload) => payload.appId),
  );

  for (const payload of acceptedPayloads) {
    for (const cell of payload.cells) {
      const embed = matchedPayloadCells.get(cell);
      // Static-only payload apps render from HTML and do not need a Pyodide
      // session.
      if (!reactivePayloadAppIds.has(payload.appId)) {
        continue;
      }

      let app = apps.get(payload.appId);
      if (!app) {
        app = { id: payload.appId, payloadBacked: true, cells: [] };
        apps.set(payload.appId, app);
      }

      const idx = app.cells.length;
      const appCell: MarimoIslandCell = {
        cellId: cell.cellId,
        output: cell.outputHtml,
        code: cell.reactive ? cell.code : "",
        idx: idx,
      };
      // Keep static cells in the generated file so later reactive cells keep
      // stable runtime indices without executing static code.
      if (!cell.reactive) {
        appCell.disabled = true;
      }
      app.cells.push(appCell);
      if (cell.reactive) {
        embed?.setAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX, idx.toString());
      }
    }
  }

  // A supported payload is the runtime source for its app. Extra same-app DOM
  // islands are disconnected from runtime binding.
  for (const embed of embeds) {
    const appId = embed.getAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID);
    if (appId && payloadAppIds.has(appId) && !consumedEmbeds.has(embed)) {
      embed.removeAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID);
      embed.removeAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX);
      embed.setAttribute(ISLAND_DATA_ATTRIBUTES.REACTIVE, "false");
    }
  }

  const domOnlyEmbeds = embeds.filter((embed) => {
    const appId = embed.getAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID);
    return !appId || !payloadAppIds.has(appId);
  });

  return [...apps.values(), ...parseIslandElementsIntoApps(domOnlyEmbeds)];
}

function findMatchingIsland({
  embeds,
  appId,
  cell,
  consumedEmbeds,
}: {
  embeds: HTMLElement[];
  appId: string;
  cell: MarimoIslandPayloadCell;
  consumedEmbeds: Set<HTMLElement>;
}): HTMLElement | undefined {
  return embeds.find((embed) => {
    if (consumedEmbeds.has(embed)) {
      return false;
    }
    return (
      embed.getAttribute(ISLAND_DATA_ATTRIBUTES.APP_ID) === appId &&
      embed.getAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID) === cell.cellId
    );
  });
}

function materializeIslandPayload(
  embed: HTMLElement,
  cell: MarimoIslandPayloadCell,
): void {
  embed.setAttribute(
    ISLAND_DATA_ATTRIBUTES.REACTIVE,
    JSON.stringify(cell.reactive),
  );
  // The runtime file is synthesized from payload order, so DOM anchors bind
  // by index.
  embed.removeAttribute(ISLAND_DATA_ATTRIBUTES.CELL_ID);
  if (!cell.reactive) {
    embed.removeAttribute(ISLAND_DATA_ATTRIBUTES.CELL_IDX);
  }

  const output = ensureIslandChild(embed, ISLAND_TAG_NAMES.CELL_OUTPUT);
  output.innerHTML = cell.displayOutput ? cell.outputHtml : "";

  const code = ensureIslandChild(embed, ISLAND_TAG_NAMES.CELL_CODE);
  code.hidden = true;
  code.textContent = encodeURIComponent(cell.code);

  const editor = embed.querySelector<HTMLElement>(ISLAND_TAG_NAMES.CODE_EDITOR);
  if (editor) {
    editor.setAttribute("data-initial-value", JSON.stringify(cell.code));
  }
}

function ensureIslandChild(embed: HTMLElement, tagName: string): HTMLElement {
  let child = embed.querySelector<HTMLElement>(tagName);
  if (!child) {
    child = embed.ownerDocument.createElement(tagName);
    embed.appendChild(child);
  }
  return child;
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

export function createMarimoFile(app: {
  cells: { code: string; disabled?: boolean }[];
}): string {
  const lines = [
    "import marimo",
    "app = marimo.App()",
    app.cells
      .map((cell) => {
        // Disabled payload cells are placeholders. Emit pass so static code
        // does not define names in the runtime graph.
        const sourceCode = cell.disabled ? "" : cell.code;
        const code = sourceCode
          ? sourceCode
              .split("\n")
              .map((line) => `    ${line}`)
              .join("\n")
          : "    pass";

        // TODO: Handle async cells better
        // This is probably not the best way to check if the code is async
        // Ideally this is pushed into the Python code
        const isAsync = code.includes("await ");
        const prefix = isAsync ? "async def" : "def";
        const decorator = cell.disabled
          ? "@app.cell(disabled=True)"
          : "@app.cell";

        // Wrap in a function
        return `${decorator}\n${prefix} __():\n${code}\n    return`;
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

function parseMarimoIslandPayloads(
  root: Document | Element,
): MarimoIslandPayload[] {
  const scripts = root.querySelectorAll<HTMLScriptElement>(
    `script[type="${ISLANDS_JSON_SCRIPT_TYPE}"]`,
  );
  const payloads: MarimoIslandPayload[] = [];

  for (const script of scripts) {
    if (isNestedIslandPayloadScript(script)) {
      continue;
    }
    const payload = parseMarimoIslandPayload(script.textContent);
    if (payload) {
      payloads.push(payload);
    }
  }

  return payloads;
}

function isNestedIslandPayloadScript(script: HTMLScriptElement): boolean {
  return Boolean(
    script.closest(ISLAND_TAG_NAMES.ISLAND) ||
    script.closest(ISLAND_TAG_NAMES.CELL_OUTPUT),
  );
}

function parseMarimoIslandPayload(
  text: string | undefined | null,
): MarimoIslandPayload | null {
  if (!text) {
    return null;
  }

  try {
    const payload = JSON.parse(text);
    if (isMarimoIslandPayload(payload)) {
      return payload;
    }
  } catch {
    return null;
  }

  return null;
}

function isMarimoIslandPayload(
  payload: unknown,
): payload is MarimoIslandPayload {
  if (!isRecord(payload)) {
    return false;
  }
  return (
    payload.schemaVersion === 1 &&
    typeof payload.appId === "string" &&
    Array.isArray(payload.cells) &&
    payload.cells.every(isMarimoIslandPayloadCell)
  );
}

function isMarimoIslandPayloadCell(
  cell: unknown,
): cell is MarimoIslandPayloadCell {
  if (!isRecord(cell)) {
    return false;
  }
  return (
    typeof cell.cellId === "string" &&
    typeof cell.code === "string" &&
    typeof cell.outputHtml === "string" &&
    typeof cell.reactive === "boolean" &&
    typeof cell.displayCode === "boolean" &&
    typeof cell.displayOutput === "boolean"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
