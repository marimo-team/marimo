/* Copyright 2026 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import type { MimeType } from "@/components/editor/Output";
import { toast } from "@/components/ui/use-toast";
import { appConfigAtom } from "@/core/config/config";
import { useInterval } from "@/hooks/useInterval";
import { AsyncCaptureTracker } from "@/utils/async-capture-tracker";
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

// MIME types to capture screenshots for
const MIME_TYPES_TO_CAPTURE_SCREENSHOTS = new Set<MimeType>([
  "text/html",
  "application/vnd.vegalite.v5+json",
  "application/vnd.vega.v5+json",
  "application/vnd.vegalite.v6+json",
  "application/vnd.vega.v6+json",
]);

type ScreenshotResult = ["image/png", string];
type ScreenshotResults = Record<CellId, ScreenshotResult>;

// Only marks cells as captured after successful screenshot.
export const captureTracker = new AsyncCaptureTracker<
  CellId,
  ScreenshotResult
>();

interface UseEnrichCellOutputsOptions {
  progress: ProgressState;
}

/**
 * Take screenshots of cells with HTML outputs. These images will be sent to the backend to be exported to IPYNB.
 * @returns A map of cell IDs to their screenshots data.
 */
export function useEnrichCellOutputs(): (
  opts: UseEnrichCellOutputsOptions,
) => Promise<ScreenshotResults> {
  const cellRuntimes = useAtomValue(cellsRuntimeAtom);

  return async (
    opts: UseEnrichCellOutputsOptions,
  ): Promise<ScreenshotResults> => {
    const { progress } = opts;

    // Prune tracked state for cells that no longer exist
    const currentCellIds = new Set(Objects.keys(cellRuntimes));
    captureTracker.prune(currentCellIds);

    const cellsToCaptureScreenshot: [CellId, unknown][] = [];
    const inFlightWaiters: {
      cellId: CellId;
      promise: Promise<ScreenshotResult | undefined>;
    }[] = [];

    for (const [cellId, runtime] of Objects.entries(cellRuntimes)) {
      const outputData = runtime.output?.data;
      if (
        runtime.output?.mimetype &&
        MIME_TYPES_TO_CAPTURE_SCREENSHOTS.has(runtime.output.mimetype) &&
        outputData
      ) {
        if (captureTracker.needsCapture(cellId, outputData)) {
          cellsToCaptureScreenshot.push([cellId, outputData]);
        } else {
          // If already in-flight with the same value, await its result
          const promise = captureTracker.waitForInFlight(cellId, outputData);
          if (promise) {
            inFlightWaiters.push({ cellId, promise });
          }
        }
      }
    }

    if (cellsToCaptureScreenshot.length === 0 && inFlightWaiters.length === 0) {
      return {};
    }

    // Start the progress bar for new captures only
    if (cellsToCaptureScreenshot.length > 0) {
      progress.addTotal(cellsToCaptureScreenshot.length);
    }

    // Capture screenshots — each key gets its own AbortSignal so
    // aborting one cell does not affect the others.
    const results: ScreenshotResults = {};
    for (const [cellId, outputData] of cellsToCaptureScreenshot) {
      const handle = captureTracker.startCapture(cellId, outputData);
      try {
        const dataUrl = await getImageDataUrlForCell(cellId);
        if (handle.signal.aborted) {
          continue;
        }
        if (!dataUrl) {
          Logger.error(`Failed to capture screenshot for cell ${cellId}`);
          handle.markFailed();
          continue;
        }
        const result: ScreenshotResult = ["image/png", dataUrl];
        results[cellId] = result;
        handle.markCaptured(result);
      } catch (error) {
        Logger.error(`Error screenshotting cell ${cellId}:`, error);
        handle.markFailed();
      } finally {
        progress.increment(1);
      }
    }

    // Await in-flight captures started by concurrent callers
    const settled = await Promise.allSettled(
      inFlightWaiters.map(({ promise }) => promise),
    );
    for (const [i, { cellId }] of inFlightWaiters.entries()) {
      const settledResult = settled[i];
      if (settledResult.status === "fulfilled" && settledResult.value) {
        results[cellId] = settledResult.value;
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
