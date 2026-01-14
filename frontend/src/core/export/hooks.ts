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
      const cellsToOutput = await takeScreenshots();
      if (Object.keys(cellsToOutput).length > 0) {
        await updateCellOutputs({
          cellIdsToOutput: cellsToOutput,
        });
      }
      await autoExportAsIPYNB({
        download: false,
      });
    },
    // Run every 5 seconds, or when the document becomes visible
    // Ignore if the document is not visible
    { delayMs: DELAY, whenVisible: true, disabled: ipynbDisabled },
  );
}

// We track cells that need screenshots, these will be exported to IPYNB
const richCellsToOutputAtom = atom<Record<CellId, unknown>>({});

export function useEnrichCellOutputs() {
  const [richCellsOutput, setRichCellsOutput] = useAtom(richCellsToOutputAtom);
  const cellRuntimes = useAtomValue(cellsRuntimeAtom);

  return async (): Promise<Record<CellId, ["image/png", unknown]>> => {
    const cellsToCaptureScreenshot = Objects.entries(cellRuntimes).filter(
      ([cellId, runtime]) => {
        const outputHasChanged =
          richCellsOutput[cellId] !== runtime.output?.data;

        return (
          runtime.output?.mimetype === "text/html" &&
          runtime.output.data &&
          outputHasChanged
        );
      },
    );

    if (cellsToCaptureScreenshot.length === 0) {
      return {};
    }

    const newCellsOutput: Record<CellId, unknown> = {};
    for (const [cellId, runtime] of cellsToCaptureScreenshot) {
      if (runtime.output?.data) {
        newCellsOutput[cellId] = runtime.output.data;
      }
    }
    setRichCellsOutput((prev) => ({ ...prev, ...newCellsOutput }));

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
