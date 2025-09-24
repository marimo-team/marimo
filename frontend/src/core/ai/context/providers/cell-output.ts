/* Copyright 2024 Marimo. All rights reserved. */

import type { Completion } from "@codemirror/autocomplete";
import type { FileUIPart } from "ai";
import { toPng } from "html-to-image";
import { notebookAtom } from "@/core/cells/cells";
import { type CellId, CellOutputId } from "@/core/cells/ids";
import { displayCellName } from "@/core/cells/names";
import { isOutputEmpty } from "@/core/cells/outputs";
import type { OutputMessage } from "@/core/kernel/messages";
import type { JotaiStore } from "@/core/state/jotai";
import { parseHtmlContent } from "@/utils/dom";
import { Logger } from "@/utils/Logger";
import { type AIContextItem, AIContextProvider } from "../registry";
import { contextToXml } from "../utils";
import { Boosts } from "./common";

export interface CellOutputContextItem extends AIContextItem {
  type: "cell-output";
  data: {
    cellId: CellId;
    cellName: string;
    cellCode: string;
    output: OutputMessage;
    outputType: "text" | "media";
    processedContent?: string;
    imageUrl?: string;
    shouldDownloadImage?: boolean;
  };
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

    for (const [cellIndex, cellId] of notebook.cellIds.inOrderIds.entries()) {
      const cellRuntime = notebook.cellRuntime[cellId];

      // Filter to only cells with output
      if (!cellRuntime?.output || isOutputEmpty(cellRuntime.output)) {
        continue;
      }

      const cellData = notebook.cellData[cellId];
      const output = cellRuntime.output;
      const mimetype = output.mimetype;

      // Determine output type
      const isMedia = isMediaMimetype(mimetype, String(output.data));
      const outputType = isMedia ? "media" : "text";

      const cellName = displayCellName(cellData.name, cellIndex);

      let processedContent: string | undefined;
      let imageUrl: string | undefined;
      let shouldDownloadImage = false;

      // Process text content
      if (outputType === "text" && typeof output.data === "string") {
        processedContent =
          mimetype === "text/html"
            ? parseHtmlContent(output.data)
            : output.data;
      }

      // Process media content - for now, we'll just note that it's media
      if (outputType === "media") {
        if (
          typeof output.data === "string" &&
          output.data.startsWith("data:")
        ) {
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

      items.push({
        uri: this.asURI(cellId),
        name: cellName,
        type: this.contextType,
        description: `Cell output (${mimetype || "unknown"})`,
        data: {
          cellId,
          cellName,
          cellCode: cellData?.code || "",
          output,
          outputType,
          processedContent,
          imageUrl,
          shouldDownloadImage,
        },
      });
    }

    return items;
  }

  formatCompletion(item: CellOutputContextItem): Completion {
    const { data } = item;
    return {
      label: `@${data.cellName}`,
      displayLabel: data.cellName,
      detail: `${data.outputType} output`,
      boost: Boosts.CELL_OUTPUT,
      type: this.contextType,
      section: "Cell Output",
      apply: `@${data.cellName}`,
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
        nameDiv.textContent = data.cellName;
        headerDiv.append(nameDiv);

        const descriptionDiv = document.createElement("div");
        descriptionDiv.classList.add("text-sm", "text-muted-foreground");
        headerDiv.append(descriptionDiv);

        infoContainer.append(headerDiv);

        // Show cell code preview
        if (data.cellCode) {
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
            data.cellCode.slice(0, 200) +
            (data.cellCode.length > 200 ? "..." : "");
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
          mediaDiv.textContent =
            "Contains media content (image, SVG, or canvas)";
          infoContainer.append(mediaDiv);
        }

        return infoContainer;
      },
    };
  }

  formatContext(item: CellOutputContextItem): string {
    const { data } = item;

    const contextData = {
      name: data.cellName,
      cellId: data.cellId,
      outputType: data.outputType,
      mimetype: data.output.mimetype,
    } as const;

    let details = `Cell Code:\n${data.cellCode}\n\n`;

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
    // Filter items that need image downloading
    const itemsNeedingDownload = items.filter(
      (item) =>
        item.data.shouldDownloadImage && item.data.outputType === "media",
    );

    if (itemsNeedingDownload.length === 0) {
      return [];
    }

    // Prepare download requests
    const downloadRequests = itemsNeedingDownload.flatMap((item) => {
      const outputElement = document.getElementById(
        CellOutputId.create(item.data.cellId),
      );
      if (!outputElement) {
        Logger.warn(`Output element not found for cell ${item.data.cellId}`);
        return [];
      }
      return {
        cellId: item.data.cellId,
        cellName: item.data.cellName,
        mimetype: item.data.output.mimetype,
        element: outputElement,
      };
    });

    try {
      return await Promise.all(
        downloadRequests.map(async (item) => ({
          type: "file",
          filename: `${item.cellName}-output-screenshot`,
          mediaType: "image/png",
          url: await toPng(item.element),
        })),
      );
    } catch (error) {
      Logger.error("Error downloading cell output images:", error);
      return [];
    }
  }
}
