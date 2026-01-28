/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useAtom, useAtomValue } from "jotai";
import type { MimeType } from "@/components/editor/Output";
import { toast } from "@/components/ui/use-toast";
import { appConfigAtom } from "@/core/config/config";
import { useInterval } from "@/hooks/useInterval";
import { getImageDataUrlForCell } from "@/utils/download";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { ProgressState } from "@/utils/progress";
import { cellsRuntimeAtom } from "../cells/cells";
import type { CellId } from "../cells/ids";
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
      const screenshotFn = () =>
        takeScreenshots({
          progress: ProgressState.indeterminate(),
          snappy: true,
        });
      await updateCellOutputsWithScreenshots({
        takeScreenshots: screenshotFn,
        updateCellOutputs,
      });
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
const MIME_TYPES_TO_CAPTURE_SCREENSHOTS = new Set<MimeType>([
  "text/html",
  "application/vnd.vegalite.v5+json",
  "application/vnd.vega.v5+json",
  "application/vnd.vegalite.v6+json",
  "application/vnd.vega.v6+json",
]);

type ScreenshotResults = Record<CellId, ["image/png", string]>;

/**
 * Take screenshots of cells with HTML outputs. These images will be sent to the backend to be exported to IPYNB.
 * @returns A map of cell IDs to their screenshots data.
 */
export function useEnrichCellOutputs() {
  const [richCellsOutput, setRichCellsOutput] = useAtom(richCellsToOutputAtom);
  const cellRuntimes = useAtomValue(cellsRuntimeAtom);

  return async ({
    progress,
    snappy,
  }: {
    progress: ProgressState;
    snappy: boolean;
  }): Promise<ScreenshotResults> => {
    const trackedCellsOutput: Record<CellId, unknown> = {};

    const cellsToCaptureScreenshot: [CellId, unknown][] = [];
    for (const [cellId, runtime] of Objects.entries(cellRuntimes)) {
      const outputData = runtime.output?.data;
      const outputHasChanged = richCellsOutput[cellId] !== outputData;
      // Track latest output for this cell
      trackedCellsOutput[cellId] = outputData;
      if (
        runtime.output?.mimetype &&
        MIME_TYPES_TO_CAPTURE_SCREENSHOTS.has(runtime.output.mimetype) &&
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
    const total = cellsToCaptureScreenshot.length;
    progress.addTotal(total);
    const results: ScreenshotResults = {};
    for (const [cellId] of cellsToCaptureScreenshot) {
      try {
        const dataUrl = await getImageDataUrlForCell(cellId, snappy);
        if (!dataUrl) {
          Logger.error(`Failed to capture screenshot for cell ${cellId}`);
          continue;
        }
        results[cellId] = ["image/png", dataUrl];
      } catch (error) {
        Logger.error(`Error screenshotting cell ${cellId}:`, error);
      } finally {
        progress.increment(1);
      }
    }

    return results;
  };
}

/**
 * Utility function to take screenshots of cells with HTML outputs and update the cell outputs.
 */
export async function updateCellOutputsWithScreenshots(opts: {
  takeScreenshots: () => Promise<ScreenshotResults>;
  updateCellOutputs: (request: UpdateCellOutputsRequest) => Promise<null>;
}) {
  const { takeScreenshots, updateCellOutputs } = opts;
  try {
    const cellIdsToOutput = await takeScreenshots();
    if (Objects.size(cellIdsToOutput) > 0) {
      await updateCellOutputs({ cellIdsToOutput });
    }
  } catch (error) {
    Logger.error("Error updating cell outputs with screenshots:", error);
    toast({
      title: "Failed to capture cell outputs",
      description:
        "Some outputs may not appear in the PDF. Continuing with export.",
      variant: "danger",
    });
  }
}
