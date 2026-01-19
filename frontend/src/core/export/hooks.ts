/* Copyright 2026 Marimo. All rights reserved. */
import { toPng } from "html-to-image";
import { atom, useAtom, useAtomValue } from "jotai";
import { appConfigAtom } from "@/core/config/config";
import { useInterval } from "@/hooks/useInterval";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { cellsRuntimeAtom } from "../cells/cells";
import { type CellId, CellOutputId } from "../cells/ids";
import { connectionAtom } from "../network/connection";
import { useRequestClient } from "../network/requests";
import type { UpdateCellOutputsRequest } from "../network/types";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import { WebSocketState } from "../websocket/types";

const DELAY = 5000; // 5 seconds;

export function useAutoExport() {
  const appConfig = useAtomValue(appConfigAtom);
  const { state } = useAtomValue(connectionAtom);

  const markdownEnabled = appConfig.auto_download.includes("markdown");
  const htmlEnabled = appConfig.auto_download.includes("html");
  const ipynbEnabled = appConfig.auto_download.includes("ipynb");

  const isConnected = state === WebSocketState.OPEN;
  const markdownDisabled = !markdownEnabled || !isConnected;
  const htmlDisabled = !htmlEnabled || !isConnected;
  const ipynbDisabled = !ipynbEnabled || !isConnected;
  const {
    autoExportAsHTML,
    autoExportAsIPYNB,
    autoExportAsMarkdown,
    updateCellOutputs,
  } = useRequestClient();
  const takeScreenshots = useEnrichCellOutputs();

  useInterval(
    async () => {
      await autoExportAsMarkdown({
        download: false,
      });
    },
    // Run every 5 seconds, or when the document becomes visible
    // Ignore if the document is not visible
    { delayMs: DELAY, whenVisible: true, disabled: markdownDisabled },
  );

  useInterval(
    async () => {
      await autoExportAsHTML({
        download: false,
        includeCode: true,
        files: VirtualFileTracker.INSTANCE.filenames(),
      });
    },
    // Run every 5 seconds, or when the document becomes visible
    // Ignore if the document is not visible
    { delayMs: DELAY, whenVisible: true, disabled: htmlDisabled },
  );

  useInterval(
    async () => {
      await updateCellOutputsWithScreenshots(
        takeScreenshots,
        updateCellOutputs,
      );
      await autoExportAsIPYNB({
        download: false,
      });
    },
    // Run every 5 seconds, or when the document becomes visible
    // Ignore if the document is not visible
    // Skip if running to ensure no race conditions between screenshot and export
    {
      delayMs: DELAY,
      whenVisible: true,
      disabled: ipynbDisabled,
      skipIfRunning: true,
    },
  );
}

// We track cells that need screenshots, these will be exported to IPYNB
const richCellsToOutputAtom = atom<Record<CellId, unknown>>({});

// MIME types to capture screenshots for
const MIME_TYPES_TO_CAPTURE_SCREENSHOTS = new Set([
  "text/html",
  "application/vnd.vegalite.v5+json",
  "application/vnd.vega.v5+json",
  "application/vnd.vegalite.v6+json",
  "application/vnd.vega.v6+json",
]);

/**
 * Take screenshots of cells with HTML outputs. These images will be sent to the backend to be exported to IPYNB.
 * @returns A map of cell IDs to their screenshots data.
 */
export function useEnrichCellOutputs() {
  const [richCellsOutput, setRichCellsOutput] = useAtom(richCellsToOutputAtom);
  const cellRuntimes = useAtomValue(cellsRuntimeAtom);

  return async (): Promise<Record<CellId, ["image/png", string]>> => {
    const trackedCellsOutput: Record<CellId, unknown> = {};

    const cellsToCaptureScreenshot: [CellId, unknown][] = [];
    for (const [cellId, runtime] of Objects.entries(cellRuntimes)) {
      const outputData = runtime.output?.data;
      const outputHasChanged = richCellsOutput[cellId] !== outputData;
      // Track latest output for this cell
      trackedCellsOutput[cellId] = outputData;
      if (
        MIME_TYPES_TO_CAPTURE_SCREENSHOTS.has(runtime.output?.mimetype ?? "") &&
        outputData &&
        outputHasChanged
      ) {
        cellsToCaptureScreenshot.push([cellId, runtime]);
      }
    }
    // Always update tracked outputs, this ensures data is fresh for the next run
    setRichCellsOutput(trackedCellsOutput);

    if (cellsToCaptureScreenshot.length === 0) {
      return {};
    }

    // Capture screenshots
    const results = await Promise.all(
      cellsToCaptureScreenshot.map(async ([cellId]) => {
        const outputElement = document.getElementById(
          CellOutputId.create(cellId),
        );
        if (!outputElement) {
          Logger.error(`Output element not found for cell ${cellId}`);
          return null;
        }

        try {
          const dataUrl = await toPng(outputElement);
          return [cellId, ["image/png", dataUrl]] as [
            CellId,
            ["image/png", string],
          ];
        } catch (error) {
          Logger.error(`Error screenshotting cell ${cellId}:`, error);
          return null;
        }
      }),
    );

    return Objects.fromEntries(
      results.filter(
        (result): result is [CellId, ["image/png", string]] => result !== null,
      ),
    );
  };
}

/**
 * Utility function to take screenshots of cells with HTML outputs and update the cell outputs.
 */
export async function updateCellOutputsWithScreenshots(
  takeScreenshots: () => Promise<Record<CellId, ["image/png", string]>>,
  updateCellOutputs: (request: UpdateCellOutputsRequest) => Promise<null>,
) {
  const cellIdsToOutput = await takeScreenshots();
  if (Object.keys(cellIdsToOutput).length > 0) {
    await updateCellOutputs({ cellIdsToOutput });
  }
}
