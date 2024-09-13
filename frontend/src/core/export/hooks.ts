/* Copyright 2024 Marimo. All rights reserved. */
import { useAtomValue } from "jotai";
import { useInterval } from "@/hooks/useInterval";
import { autoExportAsHTML, autoExportAsMarkdown } from "../network/requests";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import { connectionAtom } from "../network/connection";
import { WebSocketState } from "../websocket/types";
import { appConfigAtom } from "@/core/config/config";

const DELAY = 5000; // 5 seconds;

export function useAutoExport() {
  const appConfig = useAtomValue(appConfigAtom);
  const { state } = useAtomValue(connectionAtom);

  const markdownEnabled = appConfig.auto_download.includes("markdown");
  const htmlEnabled = appConfig.auto_download.includes("html");

  const markdownDisabled = !markdownEnabled || state !== WebSocketState.OPEN;
  const htmlDisabled = !htmlEnabled || state !== WebSocketState.OPEN;

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
}
