/* Copyright 2026 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { FileUIPart } from "ai";
import { processOutput } from "@/components/editor/output/console/process-output";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import { type CellId, CellOutputId } from "@/core/cells/ids";
import { displayCellName } from "@/core/cells/names";
import { isOutputEmpty } from "@/core/cells/outputs";
import type { OutputMessage } from "@/core/kernel/messages";
import type { JotaiStore } from "@/core/state/jotai";
import { toPng } from "@/utils/html-to-image";
import { Logger } from "@/utils/Logger";
import { type AIContextItem, AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Boosts, Sections } from "./common";

export interface BaseOutput {
  processedContent?: string;
  imageUrl?: string;
  shouldDownloadImage?: boolean;
  output: OutputMessage;
  outputType: "text" | "media";
}

export interface CellOutputData {
  cellId: CellId;
  cellName: string;
  cellCode: string;
  cellOutput?: BaseOutput;
  consoleOutputs?: BaseOutput[];
}

// For the context provider
// Currently, we enforce that cellOutput is present.
interface CellOutputContextData
  extends CellOutputData,
    Record<string, unknown> {
  cellOutput: BaseOutput;
}

export interface CellOutputContextItem extends AIContextItem {
  type: "cell-output";
  data: CellOutputContextData;
}

function isMediaMimetype(
  mimetype: OutputMessage["mimetype"] | undefined,
  htmlString: string,
): boolean {
  if (!mimetype) {
    return false;
  }

  const mediaPrefixes = ["image/", "video/", "audio/", "application/pdf"];
  if (mediaPrefixes.some((prefix) => mimetype.startsWith(prefix))) {
    return true;
  }
  const mediaIncludes = ["svg", "vega"];
  if (mediaIncludes.some((include) => mimetype.includes(include))) {
    return true;
  }

  // If it is HTML, we need to check if it contains a media tag
  if (mimetype === "text/html") {
    const mediaTags = [
      "<img",
      "<video",
      "<audio",
      "<iframe",
      "<canvas",
      "<svg",
      "<marimo-ui-element",
    ];
    if (mediaTags.some((tag) => htmlString.includes(tag))) {
      return true;
    }
  }

  return false;
}

export class CellOutputContextProvider extends AIContextProvider<CellOutputContextItem> {
  readonly title = "Cell Outputs";
  readonly mentionPrefix = "@";
  readonly contextType = "cell-output";
  private store: JotaiStore;
  constructor(store: JotaiStore) {
    super();
    this.store = store;
  }

  getItems(): CellOutputContextItem[] {
    const notebook = this.store.get(notebookAtom);
    const items: CellOutputContextItem[] = [];

    for (const cellId of notebook.cellIds.inOrderIds) {
      const cellContextData = getCellContextData(cellId, notebook);
      const cellOutput = cellContextData.cellOutput;

      // Skip cells with no output
      if (!cellOutput) {
        continue;
      }

      const mimetype = cellOutput.output.mimetype || "unknown";

      items.push({
        uri: this.asURI(cellId),
        name: cellContextData.cellName,
        type: this.contextType,
        description: `Cell output (${mimetype})`,
        data: { ...cellContextData, cellOutput },
      });
    }

    return items;
  }

  formatCompletion(item: CellOutputContextItem): Completion {
    const { cellOutput: data, cellName, cellCode } = item.data;

    return {
      label: `@${cellName}`,
      displayLabel: cellName,
      detail: `${data.outputType} output`,
      boost: data.outputType === "media" ? Boosts.HIGH : Boosts.MEDIUM,
      type: this.contextType,
      section: Sections.CELL_OUTPUT,
      apply: `@${cellName}`,
      info: () => {
        const infoContainer = document.createElement("div");
        infoContainer.classList.add(
          "mo-cm-tooltip",
          "docs-documentation",
          "min-w-[300px]",
          "max-w-[500px]",
          "flex",
          "flex-col",
          "gap-2",
        );

        const headerDiv = document.createElement("div");
        headerDiv.classList.add("flex", "flex-col", "gap-1");

        const nameDiv = document.createElement("div");
        nameDiv.classList.add("font-bold", "text-base");
        nameDiv.textContent = cellName;
        headerDiv.append(nameDiv);

        const descriptionDiv = document.createElement("div");
        descriptionDiv.classList.add("text-sm", "text-muted-foreground");
        headerDiv.append(descriptionDiv);

        infoContainer.append(headerDiv);

        // Show cell code preview
        if (cellCode) {
          const codeHeaderDiv = document.createElement("div");
          codeHeaderDiv.classList.add(
            "text-xs",
            "font-medium",
            "text-muted-foreground",
          );
          codeHeaderDiv.textContent = "Code:";
          infoContainer.append(codeHeaderDiv);

          const codeDiv = document.createElement("div");
          codeDiv.classList.add(
            "text-xs",
            "font-mono",
            "bg-muted",
            "p-2",
            "rounded",
            "max-h-20",
            "overflow-y-auto",
          );
          codeDiv.textContent =
            cellCode.slice(0, 200) + (cellCode.length > 200 ? "..." : "");
          infoContainer.append(codeDiv);
        }

        // Show output preview
        if (data.processedContent) {
          const outputHeaderDiv = document.createElement("div");
          outputHeaderDiv.classList.add(
            "text-xs",
            "font-medium",
            "text-muted-foreground",
            "mt-2",
          );
          outputHeaderDiv.textContent = "Output Preview:";
          infoContainer.append(outputHeaderDiv);

          const outputDiv = document.createElement("div");
          outputDiv.classList.add(
            "text-xs",
            "bg-muted",
            "p-2",
            "rounded",
            "max-h-24",
            "overflow-y-auto",
            "mb-2",
          );
          outputDiv.textContent =
            data.processedContent.slice(0, 300) +
            (data.processedContent.length > 300 ? "..." : "");
          infoContainer.append(outputDiv);
        }

        if (data.outputType === "media") {
          const mediaDiv = document.createElement("div");
          mediaDiv.classList.add(
            "text-xs",
            "text-muted-foreground",
            "italic",
            "mb-2",
          );
          mediaDiv.textContent = "A screenshot of the output will be attached";
          infoContainer.append(mediaDiv);
        }

        return infoContainer;
      },
    };
  }

  formatContext(item: CellOutputContextItem): string {
    const { cellOutput: data, cellName, cellId, cellCode } = item.data;

    const contextData = {
      name: cellName,
      cellId: cellId,
      outputType: data.outputType,
      mimetype: data.output.mimetype,
    } as const;

    let details = `Cell Code:\n${cellCode}\n\n`;

    if (data.outputType === "text" && data.processedContent) {
      details += `Output:\n${data.processedContent}`;
    } else if (data.outputType === "media") {
      details += `Media Output: Contains ${data.output.mimetype} content`;
      if (data.imageUrl) {
        details += `\nImage URL: ${data.imageUrl}`;
      }
    }

    return contextToXml({
      type: this.contextType,
      data: contextData,
      details,
    });
  }

  /** Get attachments for cell output items that have shouldDownloadImage=true */
  override async getAttachments(
    items: CellOutputContextItem[],
  ): Promise<FileUIPart[]> {
    const cellId = items[0].data.cellId;
    const cellName = items[0].data.cellName;
    const cellOutputs = items.map((item) => item.data.cellOutput);

    return getAttachmentsForOutputs(cellOutputs, cellId, cellName);
  }
}

export async function getAttachmentsForOutputs(
  data: BaseOutput[],
  cellId: CellId,
  cellName: string,
): Promise<FileUIPart[]> {
  // Filter items that need image downloading
  const itemsNeedingDownload = data.filter(
    (item) => item.shouldDownloadImage && item.outputType === "media",
  );

  if (itemsNeedingDownload.length === 0) {
    return [];
  }

  // Prepare download requests
  const downloadRequests = itemsNeedingDownload.flatMap((item) => {
    const outputElement = document.getElementById(CellOutputId.create(cellId));
    if (!outputElement) {
      Logger.warn(`Output element not found for cell ${cellId}`);
      return [];
    }
    return {
      cellId: cellId,
      cellName: cellName,
      mimetype: item.output.mimetype,
      element: outputElement,
    };
  });

  try {
    return await Promise.all(
      downloadRequests.map(async (item) => ({
        type: "file",
        filename: `${cellName}-output-screenshot`,
        mediaType: "image/png",
        url: await toPng(item.element),
      })),
    );
  } catch (error) {
    Logger.error("Error downloading cell output images:", error);
    return [];
  }
}

function getBaseOutput(output: OutputMessage): BaseOutput | null {
  if (isOutputEmpty(output)) {
    return null;
  }

  const mimetype = output.mimetype;

  // Determine output type
  const isMedia = isMediaMimetype(mimetype, String(output.data));
  const outputType = isMedia ? "media" : "text";

  const processedContent = processOutput(output);
  let imageUrl: string | undefined;
  let shouldDownloadImage = false;

  // Process media content - for now, we'll just note that it's media
  if (outputType === "media") {
    if (typeof output.data === "string" && output.data.startsWith("data:")) {
      imageUrl = output.data; // Data URL
    } else if (
      typeof output.data === "string" &&
      output.data.startsWith("http")
    ) {
      imageUrl = output.data; // External URL
    } else {
      // Download the image from the DOM element
      shouldDownloadImage = true;
    }
  }

  return {
    processedContent,
    imageUrl,
    shouldDownloadImage,
    outputType,
    output,
  };
}

export function getCellContextData(
  cellId: CellId,
  notebook: NotebookState,
  opts?: {
    includeConsoleOutput: boolean;
  },
): CellOutputData {
  const { includeConsoleOutput = false } = opts || {};
  const cellRuntime = notebook.cellRuntime[cellId];

  const cellData = notebook.cellData[cellId];
  const cellIndex = notebook.cellIds.inOrderIds.indexOf(cellId);
  const cellName = displayCellName(cellData.name, cellIndex);

  let consoleOutputs: BaseOutput[] | undefined;
  if (includeConsoleOutput) {
    consoleOutputs = cellRuntime.consoleOutputs
      .map((output) => getBaseOutput(output))
      .filter((output) => output !== null);
  }

  let cellOutput: BaseOutput | undefined;
  const rawCellOutput = cellRuntime.output;
  if (rawCellOutput && !isOutputEmpty(rawCellOutput)) {
    cellOutput = getBaseOutput(rawCellOutput) ?? undefined;
  }

  return {
    cellId,
    cellName,
    cellCode: cellData.code,
    cellOutput,
    consoleOutputs,
  };
}
