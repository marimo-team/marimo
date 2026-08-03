/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useEffect, useRef, useState } from "react";
import { toast } from "@/components/ui/use-toast";
import {
  updateCellOutputsWithScreenshots,
  useEnrichCellOutputs,
} from "@/core/export/hooks";
import { runDuringPresentMode, viewStateAtom } from "@/core/mode";
import { useRequestClient } from "@/core/network/requests";
import type { ExportAvailabilityResponse } from "@/core/network/types";
import { useFilename } from "@/core/saving/filename";
import { VirtualFileTracker } from "@/core/static/virtual-file-tracker";
import { isWasm } from "@/core/wasm/utils";
import { type AsyncDataResult, useAsyncData } from "@/hooks/useAsyncData";
import {
  ADD_PRINTING_CLASS,
  downloadExportedFile,
  downloadHTMLAsImage,
  withLoadingToast,
} from "@/utils/download";
import { Filenames } from "@/utils/filenames";
import { Logger } from "@/utils/Logger";
import { Paths } from "@/utils/paths";
import { getExportCommand } from "./export-command";
import { exportNotebook } from "./export-notebook";
import { FORMAT_DEFINITIONS, type UpdateExportOptions } from "./format-options";
import {
  EXPORT_FORMATS,
  type ExportFormat,
  type ExportOptions,
  exportOptionsAtom,
  getExportFormatStatus,
  isBrowserPrintExport,
  isExportFormat,
  lastExportFormatAtom,
} from "./state";

type ExportAvailability = Parameters<
  typeof getExportFormatStatus
>[0]["availability"];

const SCRIPT_EXPORT_COPY: Record<
  ExportOptions["script"]["type"],
  { actionLabel: string; progressLabel: string }
> = {
  source: {
    actionLabel: "Export notebook source",
    progressLabel: "notebook source",
  },
  flat: {
    actionLabel: "Export flat script",
    progressLabel: "flat script",
  },
};

function getExportAvailability(
  runtime: "server" | "wasm",
  request: AsyncDataResult<ExportAvailabilityResponse | null>,
): ExportAvailability {
  if (runtime === "wasm") {
    return { status: "success", data: null };
  }

  switch (request.status) {
    case "pending":
    case "loading":
      return { status: "pending" };
    case "error":
      return { status: "error" };
    case "success":
      return { status: "success", data: request.data };
  }
}

function getSourceFilename(
  runtime: "server" | "wasm",
  filename: string | null,
): string {
  if (runtime === "server" && filename) {
    return Paths.basename(filename);
  }
  return Filenames.toPY(document.title);
}

function getFooterDescription({
  usesBrowserPrint,
  hasCommand,
  format,
  isNotebookSource,
}: {
  usesBrowserPrint: boolean;
  hasCommand: boolean;
  format: ExportFormat;
  isNotebookSource: boolean;
}): string | null {
  if (usesBrowserPrint) {
    return "Uses the browser's print settings for page size and filename.";
  }
  if (hasCommand) {
    return "Uses the current session state. The copied command exports the saved notebook.";
  }
  if (format !== "png" && !isNotebookSource) {
    return "Save the notebook to copy an equivalent shell command.";
  }
  return null;
}

function useExportDialogState(initialFormat?: ExportFormat) {
  const filename = useFilename();
  const [options, setOptions] = useAtom(exportOptionsAtom);
  const [lastFormat, setLastFormat] = useAtom(lastExportFormatAtom);
  const [format, setFormat] = useState<ExportFormat>(
    initialFormat ?? lastFormat,
  );
  const runtime = isWasm() ? "wasm" : "server";
  const requests = useRequestClient();

  const availabilityRequest =
    useAsyncData<ExportAvailabilityResponse | null>(async () => {
      if (runtime === "wasm") {
        return null;
      }
      return requests.getExportAvailability();
    }, [runtime, requests]);
  const availability = getExportAvailability(runtime, availabilityRequest);

  const statusFor = (candidate: ExportFormat) =>
    getExportFormatStatus({
      format: candidate,
      options,
      runtime,
      filename,
      availability,
    });
  const status = statusFor(format);
  const formats = EXPORT_FORMATS.map((candidate) => ({
    format: candidate,
    status: statusFor(candidate),
  }));
  const usesBrowserPrint = isBrowserPrintExport(runtime, format);
  const definition = FORMAT_DEFINITIONS[format];
  const isNotebookSource =
    format === "script" && options.script.type === "source";
  const { actionLabel, progressLabel } =
    format === "script"
      ? SCRIPT_EXPORT_COPY[options.script.type]
      : {
          actionLabel: definition.actionLabel,
          progressLabel: definition.label,
        };
  const command = usesBrowserPrint
    ? null
    : getExportCommand({ format, filename, options });
  const footerDescription = getFooterDescription({
    usesBrowserPrint,
    hasCommand: Boolean(command),
    format,
    isNotebookSource,
  });

  useEffect(() => {
    if (initialFormat) {
      setLastFormat(initialFormat);
    }
  }, [initialFormat, setLastFormat]);

  const selectFormat = (value: string) => {
    if (isExportFormat(value)) {
      setFormat(value);
      setLastFormat(value);
    }
  };

  const updateOptions: UpdateExportOptions = (optionFormat, nextOptions) => {
    setOptions((current) => {
      const next = { ...current };
      next[optionFormat] = {
        ...current[optionFormat],
        ...nextOptions,
      };
      return next;
    });
  };

  return {
    formats,
    options,
    selected: {
      format,
      status,
      usesBrowserPrint,
      actionLabel,
      command,
      footerDescription,
    },
    exportRequest: {
      format,
      options,
      sourceFilename: getSourceFilename(runtime, filename),
      available: status.available,
      usesBrowserPrint,
      progressLabel,
    },
    selectFormat,
    updateOptions,
  };
}

async function captureCurrentAppView(
  dialogContainer: HTMLElement | null,
): Promise<void> {
  const app = document.getElementById("App");
  if (!app) {
    const message = "The current app view could not be captured.";
    toast({
      title: "Failed to download as PNG",
      description: message,
      variant: "danger",
    });
    throw new Error(message);
  }

  const previousVisibility = dialogContainer?.style.visibility;
  const wasCaptureExcluded =
    dialogContainer?.classList.contains("print:hidden");
  const downloaded = await downloadHTMLAsImage({
    element: app,
    filename: document.title,
    prepare: () => {
      const cleanupPrinting = ADD_PRINTING_CLASS();
      if (dialogContainer) {
        dialogContainer.classList.add("print:hidden");
        dialogContainer.style.visibility = "hidden";
      }
      return () => {
        cleanupPrinting();
        if (dialogContainer) {
          if (!wasCaptureExcluded) {
            dialogContainer.classList.remove("print:hidden");
          }
          dialogContainer.style.visibility = previousVisibility ?? "";
        }
      };
    },
  });
  if (!downloaded) {
    throw new Error("Failed to capture the current app view.");
  }
}

function printCurrentView(onClose: () => void): void {
  onClose();
  requestAnimationFrame(() => {
    setTimeout(() => {
      window.print();
    }, 0);
  });
}

function useExportDialogAction({
  format,
  options,
  sourceFilename,
  available,
  usesBrowserPrint,
  progressLabel,
  onClose,
}: {
  format: ExportFormat;
  options: ExportOptions;
  sourceFilename: string;
  available: boolean;
  usesBrowserPrint: boolean;
  progressLabel: string;
  onClose: () => void;
}) {
  const requests = useRequestClient();
  const takeScreenshots = useEnrichCellOutputs();
  const viewState = useAtomValue(viewStateAtom);
  const setViewState = useSetAtom(viewStateAtom);
  const [isExporting, setIsExporting] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const captureOutputs = async (
    progress: Parameters<typeof takeScreenshots>[0]["progress"],
  ) => {
    await updateCellOutputsWithScreenshots({
      takeScreenshots: () => takeScreenshots({ progress }),
      updateCellOutputs: requests.updateCellOutputs,
    });
  };

  const capturePNG = async () => {
    const capture = () =>
      captureCurrentAppView(dialogRef.current?.parentElement ?? null);
    if (viewState.mode !== "edit") {
      await capture();
      return;
    }
    try {
      await runDuringPresentMode(capture);
    } finally {
      setViewState(viewState);
    }
  };

  const submit = async () => {
    if (!available || isExporting) {
      return;
    }
    if (usesBrowserPrint) {
      printCurrentView(onClose);
      return;
    }

    setIsExporting(true);
    try {
      await withLoadingToast(
        `Exporting ${progressLabel}…`,
        async (progress) => {
          await exportNotebook({
            format,
            options,
            requests,
            sourceFilename,
            htmlFiles: VirtualFileTracker.INSTANCE.filenames(),
            captureOutputs: () => captureOutputs(progress),
            capturePNG,
            downloadFile: downloadExportedFile,
          });
        },
      );
      if (mountedRef.current) {
        onClose();
      }
    } catch (error) {
      // Most helpers toast actionable errors, but not all (e.g. updateCellOutputs).
      Logger.error("Export failed", error);
    } finally {
      if (mountedRef.current) {
        setIsExporting(false);
      }
    }
  };

  return { dialogRef, isExporting, submit };
}

export function useExportDialog({
  initialFormat,
  onClose,
}: {
  initialFormat?: ExportFormat;
  onClose: () => void;
}) {
  const { exportRequest, selectFormat, ...state } =
    useExportDialogState(initialFormat);
  const action = useExportDialogAction({
    ...exportRequest,
    onClose,
  });

  return {
    ...state,
    ...action,
    selectFormat: (value: string) => {
      if (!action.isExporting) {
        selectFormat(value);
      }
    },
  };
}
