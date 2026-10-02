/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import {
  AlertCircleIcon,
  BracesIcon,
  BrickWallIcon,
  ChevronRightIcon,
  ClipboardCopyIcon,
  DownloadIcon,
  FileTextIcon,
  InfoIcon,
  TableIcon,
} from "lucide-react";
import React from "react";
import { downloadSizeLimitAtom } from "./download-policy/atoms";
import type {
  DownloadAsArgs,
  DownloadAsOptions,
  DownloadFormat,
  ExportMetadata,
  GetExportMetadata,
} from "./schemas";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { downloadByURL, withLoadingToast } from "@/utils/download";
import { prettyError } from "@/utils/errors";
import { Filenames } from "@/utils/filenames";
import {
  jsonParseWithSpecialChar,
  jsonToMarkdown,
} from "@/utils/json/json-parser";
import { MissingPackagePrompt } from "../datasources/missing-package-prompt";
import { Alert, AlertDescription, AlertTitle } from "../ui/alert";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { Label } from "../ui/label";
import { NativeSelect } from "../ui/native-select";
import { Switch } from "../ui/switch";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";

const EXPORT_OPTIONS = [
  {
    label: "CSV",
    format: "csv",
    description: "Comma-separated values",
    icon: TableIcon,
    canDownload: true,
    canCopy: true,
  },
  {
    label: "TSV",
    format: "tsv",
    description: "Best for Excel and Google Sheets",
    icon: TableIcon,
    canDownload: true,
    canCopy: true,
  },
  {
    label: "JSON",
    format: "json",
    description: "Raw JSON data",
    icon: BracesIcon,
    canDownload: true,
    canCopy: true,
  },
  {
    label: "Parquet",
    format: "parquet",
    description: "Columnar binary format",
    icon: BrickWallIcon,
    canDownload: true,
    canCopy: false,
  },
  {
    label: "Markdown",
    format: "markdown",
    description: "Preserves hyperlinks and formatting",
    icon: FileTextIcon,
    canDownload: false,
    canCopy: true,
  },
] as const;

type ExportFormat = (typeof EXPORT_OPTIONS)[number]["format"];
type CopyFormat = Exclude<ExportFormat, "parquet">;
type ExportAction =
  | { destination: "download"; format: DownloadFormat }
  | { destination: "copy"; format: CopyFormat };

type ExportFailure =
  | {
      kind: "error";
      title: string;
      description: string;
      action: ExportAction;
    }
  | {
      kind: "missing-packages";
      description?: string | null;
      packages: string[];
      action: ExportAction;
    };

// Each clipboard-copy format fetches from a backend download format, then
// transforms the payload client-side as needed.
const COPY_SOURCE_FORMAT: Record<CopyFormat, DownloadFormat> = {
  csv: "csv",
  tsv: "tsv",
  json: "json",
  markdown: "json",
};

const SEPARATORS = [
  { value: ",", label: "Comma" },
  { value: ";", label: "Semicolon" },
  { value: "|", label: "Pipe" },
] as const;

const ENCODINGS = [
  { value: "utf-8", label: "UTF-8" },
  { value: "utf-8-sig", label: "UTF-8 with BOM" },
  { value: "latin-1", label: "Latin-1" },
] as const;

type Separator = (typeof SEPARATORS)[number]["value"];
type Encoding = (typeof ENCODINGS)[number]["value"];

interface ExportSettings {
  csv: { separator: Separator; encoding: Encoding };
  tsv: { encoding: Encoding };
  json: { ensureAscii: boolean };
}

const DEFAULT_SETTINGS: ExportSettings = {
  csv: { separator: ",", encoding: "utf-8" },
  tsv: { encoding: "utf-8" },
  json: { ensureAscii: true },
};

type ConfigurableFormat = keyof ExportSettings;

const isConfigurable = (format: ExportFormat): format is keyof ExportSettings =>
  format in DEFAULT_SETTINGS;

/**
 * Build the request options for one action. Only settings that differ from
 * the defaults are sent, so the backend keeps its own defaults otherwise.
 *
 * Clipboard copies never send an encoding. The browser decodes the fetched
 * payload as UTF-8, so any other encoding would corrupt the copied text.
 */
function requestOptions(
  settings: ExportSettings,
  format: DownloadFormat,
  destination: ExportAction["destination"],
): DownloadAsOptions | undefined {
  const options: DownloadAsOptions = {};
  switch (format) {
    case "csv":
      if (settings.csv.separator !== DEFAULT_SETTINGS.csv.separator) {
        options.separator = settings.csv.separator;
      }
      if (
        destination === "download" &&
        settings.csv.encoding !== DEFAULT_SETTINGS.csv.encoding
      ) {
        options.encoding = settings.csv.encoding;
      }
      break;
    case "tsv":
      if (
        destination === "download" &&
        settings.tsv.encoding !== DEFAULT_SETTINGS.tsv.encoding
      ) {
        options.encoding = settings.tsv.encoding;
      }
      break;
    case "json":
      if (settings.json.ensureAscii !== DEFAULT_SETTINGS.json.ensureAscii) {
        options.ensure_ascii = settings.json.ensureAscii;
      }
      break;
    case "parquet":
      break;
    default:
      logNever(format);
  }
  return Object.keys(options).length > 0 ? options : undefined;
}

const labelForValue = (
  items: ReadonlyArray<{ value: string; label: string }>,
  value: string,
): string => items.find((item) => item.value === value)?.label ?? value;

/** Short summary of the current settings, shown next to the format label. */
function settingsSummary(
  settings: ExportSettings,
  format: ExportFormat,
): string | null {
  switch (format) {
    case "csv":
      return [
        labelForValue(SEPARATORS, settings.csv.separator),
        labelForValue(ENCODINGS, settings.csv.encoding),
      ].join(" · ");
    case "tsv":
      return labelForValue(ENCODINGS, settings.tsv.encoding);
    case "json":
      return settings.json.ensureAscii
        ? "Escapes non-ASCII"
        : "Keeps non-ASCII";
    case "parquet":
    case "markdown":
      return null;
    default:
      logNever(format);
      return null;
  }
}

export interface ExportActionProps {
  downloadAs: DownloadAsArgs;
  getExportMetadata?: GetExportMetadata;
  metadataSource?: unknown;
  // JSON-serialized size of the currently-rendered data. Used together with
  // downloadSizeLimitAtom to disable the Export button when a host (e.g.,
  // marimo-lsp inside VS Code) declares a download size cap. Null/undefined
  // means "no info" and the gate stays disabled (fail-open).
  sizeBytes?: number | null;
  sizeBytesIsLoading?: boolean;
}

const labelForFormat = (format: ExportFormat, hasGeometry = false): string =>
  format === "parquet" && hasGeometry
    ? "GeoParquet"
    : (EXPORT_OPTIONS.find((option) => option.format === format)?.label ??
      format);

const failureTitleForAction = (action: ExportAction): string =>
  action.destination === "download"
    ? "Failed to download"
    : "Failed to copy to clipboard";

const failureDescription = (error: unknown): string =>
  typeof error === "string" ? error : prettyError(error);

export const ExportActions: React.FC<ExportActionProps> = (props) => {
  const { getExportMetadata, metadataSource } = props;
  const [exportDialogOpen, setExportDialogOpen] = React.useState(false);
  const [failure, setFailure] = React.useState<ExportFailure | null>(null);
  const [settings, setSettings] =
    React.useState<ExportSettings>(DEFAULT_SETTINGS);
  const [metadata, setMetadata] = React.useState<ExportMetadata | null>(null);
  const [metadataLoading, setMetadataLoading] = React.useState(false);
  const [metadataError, setMetadataError] = React.useState<string | null>(null);
  const [metadataRefresh, setMetadataRefresh] = React.useState(0);
  const [geometryColumn, setGeometryColumn] = React.useState<string | null>(
    null,
  );
  const hasGeometry = !!metadata?.geometry_columns.length;
  const [expandedFormat, setExpandedFormat] = React.useState<
    ConfigurableFormat | "parquet" | null
  >(null);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const dialogRef = React.useRef<HTMLDivElement>(null);
  const latestActionId = React.useRef(0);
  React.useEffect(() => {
    latestActionId.current += 1;
  }, [metadataSource]);
  React.useEffect(() => {
    if (!exportDialogOpen || !getExportMetadata) {
      return;
    }
    let active = true;
    setMetadata(null);
    setMetadataLoading(true);
    setMetadataError(null);
    void getExportMetadata({}).then(
      (result) => {
        if (!active) {
          return;
        }
        setMetadata(result);
        setGeometryColumn((current) =>
          current !== null &&
          result.geometry_columns.some((column) => column.name === current)
            ? current
            : result.default_geometry_column,
        );
        setMetadataLoading(false);
      },
      (error: unknown) => {
        if (!active) {
          return;
        }
        setMetadataError(failureDescription(error));
        setMetadataLoading(false);
      },
    );
    return () => {
      active = false;
    };
  }, [exportDialogOpen, getExportMetadata, metadataSource, metadataRefresh]);
  const policy = useAtomValue(downloadSizeLimitAtom);
  const overLimit = !!(
    policy &&
    props.sizeBytes != null &&
    props.sizeBytes > policy.limitBytes
  );
  const disabled = !!(policy && (props.sizeBytesIsLoading || overLimit));
  const tooltipContent = !disabled
    ? "Export"
    : props.sizeBytesIsLoading
      ? "Checking download size…"
      : policy?.unavailableMessage;

  const button = (
    <Button
      ref={triggerRef}
      data-testid="export-button"
      size="xs"
      variant="text"
      disabled={disabled}
      className={cn(
        "print:hidden text-xs gap-1",
        exportDialogOpen ? "text-primary" : "text-muted-foreground",
      )}
    >
      <DownloadIcon className="w-3.5 h-3.5" />
      Export
    </Button>
  );

  const handleDialogOpenChange = (open: boolean) => {
    setExportDialogOpen(open);
    if (!open) {
      latestActionId.current += 1;
      setFailure(null);
      setExpandedFormat(null);
      setSettings(DEFAULT_SETTINGS);
      setMetadata(null);
      setMetadataError(null);
      setGeometryColumn(null);
    }
  };

  const beginAction = () => {
    const actionId = latestActionId.current + 1;
    latestActionId.current = actionId;
    setFailure(null);
    return actionId;
  };

  const setActionFailure = (actionId: number, nextFailure: ExportFailure) => {
    if (actionId === latestActionId.current) {
      setFailure(nextFailure);
    }
  };

  const resolveDownloadUrl = async (
    format: DownloadFormat,
    action: ExportAction,
    actionId: number,
  ): Promise<{
    url: string;
    filename: string;
  } | null> => {
    const options = requestOptions(settings, format, action.destination);
    const request = {
      format,
      ...(options ? { options } : {}),
      ...(format === "parquet" && geometryColumn !== null
        ? { geometry_column: geometryColumn }
        : {}),
    };
    const response = await props.downloadAs(request);
    if (actionId !== latestActionId.current) {
      return null;
    }

    if (response.missing_packages && response.missing_packages.length > 0) {
      setActionFailure(actionId, {
        kind: "missing-packages",
        packages: response.missing_packages,
        description: response.error,
        action,
      });
      return null;
    }

    if (response.error || response.code || !response.url) {
      setActionFailure(actionId, {
        kind: "error",
        title: failureTitleForAction(action),
        description: response.error ?? "The export did not produce a file.",
        action,
      });
      return null;
    }

    return {
      url: response.url,
      filename: response.filename,
    };
  };

  const handleDownload = async (format: DownloadFormat) => {
    const action: ExportAction = { destination: "download", format };
    const actionId = beginAction();
    const label = labelForFormat(format, hasGeometry);
    try {
      const ok = await withLoadingToast(
        `Preparing ${label} export...`,
        async () => {
          const result = await resolveDownloadUrl(format, action, actionId);
          if (!result) {
            return false;
          }
          if (actionId !== latestActionId.current) {
            return false;
          }
          const rawName = (result.filename ?? "").trim();
          const baseName = Filenames.withoutExtension(rawName) || "download";
          const downloadName = `${baseName}.${format}`;
          // Append ?download=1 so the server returns Content-Disposition: attachment.
          // This forces a save even when <a download> is ignored — e.g., inside
          // sandboxed iframes that lack `allow-downloads`. Skip for data: URLs
          // (used in pyodide/wasm) since query params would corrupt the payload.
          let downloadUrl = result.url;
          if (!downloadUrl.startsWith("data:")) {
            const separator = downloadUrl.includes("?") ? "&" : "?";
            const params = new URLSearchParams({
              download: "1",
              filename: downloadName,
            });
            downloadUrl = `${downloadUrl}${separator}${params.toString()}`;
          }
          downloadByURL(downloadUrl, downloadName);
          return true;
        },
      );
      if (ok) {
        toast({ title: `${label} download started` });
      }
    } catch (error) {
      setActionFailure(actionId, {
        kind: "error",
        title: failureTitleForAction(action),
        description: failureDescription(error),
        action,
      });
    }
  };

  const handleClipboardCopy = async (
    format: CopyFormat,
    action: ExportAction,
    actionId: number,
  ) => {
    await withLoadingToast(
      `Preparing ${labelForFormat(format, hasGeometry)} for clipboard...`,
      async () => {
        const sourceFormat = COPY_SOURCE_FORMAT[format];
        const result = await resolveDownloadUrl(sourceFormat, action, actionId);
        if (!result) {
          return;
        }

        let text: string;
        switch (format) {
          case "tsv":
          case "csv":
            text = await fetchText(result.url);
            break;
          case "json": {
            const json = await fetchJson(result.url);
            text = JSON.stringify(json, null, 2);
            break;
          }
          case "markdown": {
            const json = await fetchJson(result.url);
            text = jsonToMarkdown(json);
            break;
          }
          default:
            logNever(format);
            return;
        }

        await copyToClipboard(text);
        toast({
          title: "Copied to clipboard",
        });
        handleDialogOpenChange(false);
      },
    );
  };

  const handleCopyAction = async (format: CopyFormat) => {
    const action: ExportAction = { destination: "copy", format };
    const actionId = beginAction();
    try {
      await handleClipboardCopy(format, action, actionId);
    } catch (error) {
      setActionFailure(actionId, {
        kind: "error",
        title: failureTitleForAction(action),
        description: failureDescription(error),
        action,
      });
    }
  };

  const retryAction = (action: ExportAction) => {
    if (action.destination === "download") {
      void handleDownload(action.format);
    } else {
      void handleCopyAction(action.format);
    }
  };

  const retryAfterInstall = async (action: ExportAction) => {
    if (action.format === "parquet" && getExportMetadata) {
      const actionId = latestActionId.current;
      let result: ExportMetadata;
      try {
        result = await getExportMetadata({});
      } catch (error) {
        if (actionId === latestActionId.current) {
          setMetadataError(failureDescription(error));
        }
        return;
      }
      if (actionId !== latestActionId.current) {
        return;
      }
      setMetadata(result);
      setMetadataError(null);
      if (result.formats.parquet?.available === false) {
        setFailure(null);
        return;
      }
      if (
        geometryColumn !== null &&
        !result.geometry_columns.some(
          (column) => column.name === geometryColumn,
        )
      ) {
        setGeometryColumn(result.default_geometry_column);
        setActionFailure(actionId, {
          kind: "error",
          title: failureTitleForAction(action),
          description:
            "The selected geometry is no longer available. Choose another geometry to export.",
          action,
        });
        return;
      }
      if (result.geometry_columns.length > 0 && geometryColumn === null) {
        return;
      }
    }
    retryAction(action);
  };

  const toggleExpanded = (format: ExportFormat) => {
    if (
      !isConfigurable(format) &&
      !(format === "parquet" && metadata?.geometry_columns.length)
    ) {
      return;
    }
    setExpandedFormat((current) => (current === format ? null : format));
  };

  return (
    <Dialog open={exportDialogOpen} onOpenChange={handleDialogOpenChange}>
      <Tooltip content={tooltipContent}>
        {disabled ? (
          // Keep the host-limit reason reachable when the nested button is disabled.
          // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          <span tabIndex={0} className="inline-flex">
            {button}
          </span>
        ) : (
          <DialogTrigger asChild={true}>{button}</DialogTrigger>
        )}
      </Tooltip>
      <DialogContent
        ref={dialogRef}
        className="print:hidden gap-4 sm:max-w-[540px]"
        onOpenAutoFocus={(event) => {
          event.preventDefault();
          dialogRef.current?.focus();
        }}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          triggerRef.current?.focus();
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") {
            handleDialogOpenChange(false);
          }
        }}
      >
        <DialogHeader>
          <DialogTitle>Export table</DialogTitle>
          <DialogDescription>
            Download a file or copy to the clipboard.
          </DialogDescription>
        </DialogHeader>
        <ul
          aria-label="Export formats"
          className="list-none overflow-hidden rounded-md border divide-y"
        >
          {EXPORT_OPTIONS.map((option) => {
            const optionLabel = labelForFormat(option.format, hasGeometry);
            const configurableFormat =
              isConfigurable(option.format) ||
              (option.format === "parquet" &&
                !!metadata?.geometry_columns.length)
                ? option.format
                : null;
            const expanded =
              configurableFormat !== null &&
              expandedFormat === configurableFormat;
            const panelId = `export-options-${option.format}`;
            const rowFailure =
              failure?.action.format === option.format ? failure : null;
            const summary =
              option.format === "parquet" && metadata?.geometry_columns.length
                ? geometryColumn === ""
                  ? "(unnamed geometry)"
                  : (geometryColumn ?? "Choose geometry")
                : settingsSummary(settings, option.format);
            const selectedGeometryIndex =
              metadata?.geometry_columns.findIndex(
                (column) => column.name === geometryColumn,
              ) ?? -1;
            const parquetEligibility =
              option.format === "parquet"
                ? metadata?.formats.parquet
                : undefined;
            const missingPackageFailure =
              rowFailure?.kind === "missing-packages" ? rowFailure : null;
            const missingPackages =
              missingPackageFailure?.packages ??
              (parquetEligibility?.available === false
                ? parquetEligibility.missing_packages
                : []);
            const parquetUnavailable =
              option.format === "parquet" &&
              ((!!getExportMetadata && !metadata) ||
                metadataLoading ||
                !!metadataError ||
                parquetEligibility?.available === false ||
                (!!metadata?.geometry_columns.length &&
                  geometryColumn === null));
            return (
              <li
                key={option.format}
                data-testid={`export-row-${option.format}`}
                className={cn(expanded && "bg-muted/40")}
              >
                <div className="grid min-h-[60px] grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-x-1 px-2.5 py-2 hover:bg-accent/50">
                  {configurableFormat ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`${optionLabel} options`}
                      aria-expanded={expanded}
                      aria-controls={panelId}
                      onClick={() => toggleExpanded(option.format)}
                    >
                      <ChevronRightIcon
                        className={cn(
                          "h-4 w-4 text-muted-foreground transition-transform",
                          expanded && "rotate-90",
                        )}
                      />
                    </Button>
                  ) : (
                    <span aria-hidden={true} className="h-6 w-6" />
                  )}
                  <div className="flex min-w-0 items-center gap-3 pl-1">
                    <option.icon
                      aria-hidden={true}
                      data-testid={`export-format-icon-${option.format}`}
                      className="h-4 w-4 shrink-0 text-muted-foreground"
                    />
                    <div className="grid min-w-0 gap-1">
                      <span className="flex min-w-0 items-baseline gap-x-2">
                        <span className="text-sm font-medium leading-tight">
                          {optionLabel}
                        </span>
                        {summary && (
                          <span
                            data-testid={`export-summary-${option.format}`}
                            className="min-w-0 truncate text-xs text-muted-foreground"
                          >
                            {summary}
                          </span>
                        )}
                      </span>
                      <span className="text-xs text-muted-foreground leading-tight">
                        {option.format === "parquet" && hasGeometry
                          ? "Parquet with geometry and CRS metadata"
                          : option.description}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Tooltip
                      content={
                        option.canDownload
                          ? `Download ${optionLabel}`
                          : `${optionLabel} is available for copy only.`
                      }
                    >
                      <span className="inline-flex">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Download ${optionLabel}`}
                          disabled={
                            !option.canDownload ||
                            parquetUnavailable ||
                            missingPackages.length > 0
                          }
                          onClick={
                            option.canDownload &&
                            !parquetUnavailable &&
                            missingPackages.length === 0
                              ? () => {
                                  void handleDownload(option.format);
                                }
                              : undefined
                          }
                        >
                          <DownloadIcon className="h-4 w-4" />
                        </Button>
                      </span>
                    </Tooltip>
                    <Tooltip
                      content={
                        option.canCopy
                          ? `Copy ${optionLabel}`
                          : `${optionLabel} is available for download only.`
                      }
                    >
                      <span className="inline-flex">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Copy ${optionLabel}`}
                          disabled={!option.canCopy}
                          onClick={
                            option.canCopy
                              ? () => {
                                  void handleCopyAction(option.format);
                                }
                              : undefined
                          }
                        >
                          <ClipboardCopyIcon className="h-4 w-4" />
                        </Button>
                      </span>
                    </Tooltip>
                  </div>
                </div>
                {expanded && configurableFormat && (
                  <fieldset
                    id={panelId}
                    className="grid grid-cols-2 gap-3 border-t bg-muted/50 px-3.5 py-3.5 pl-[52px]"
                  >
                    <legend className="sr-only">{optionLabel} options</legend>
                    {configurableFormat === "parquet" ? (
                      <SettingField
                        id="export-primary-geometry"
                        label="Primary geometry"
                        help="Geometry column to use as the primary geometry in the GeoParquet file."
                      >
                        <NativeSelect
                          id="export-primary-geometry"
                          className="mb-0 w-full"
                          value={String(selectedGeometryIndex)}
                          onChange={(event) => {
                            const index = Number(event.target.value);
                            setGeometryColumn(
                              metadata?.geometry_columns[index]?.name ?? null,
                            );
                          }}
                        >
                          <option value="-1" disabled={true}>
                            Choose geometry
                          </option>
                          {metadata?.geometry_columns.map((column, index) => (
                            <option key={column.name} value={String(index)}>
                              {column.name || "(unnamed geometry)"}
                            </option>
                          ))}
                        </NativeSelect>
                      </SettingField>
                    ) : (
                      <ExportSettingsFields
                        format={configurableFormat}
                        settings={settings}
                        onChange={setSettings}
                      />
                    )}
                  </fieldset>
                )}
                {option.format === "parquet" &&
                  missingPackages.length === 0 &&
                  (parquetEligibility?.reason ||
                    metadataError ||
                    (!!metadata?.geometry_columns.length &&
                      geometryColumn === null)) && (
                    <div className="flex items-center justify-between gap-2 border-t px-3 py-2 pl-[42px] text-xs text-muted-foreground">
                      <span>
                        {metadataError
                          ? `Could not load geometry options: ${metadataError}`
                          : (parquetEligibility?.reason ??
                            "Choose a primary geometry column to export GeoParquet.")}
                      </span>
                      {metadataError && (
                        <Button
                          type="button"
                          size="xs"
                          variant="outline"
                          onClick={() =>
                            setMetadataRefresh((current) => current + 1)
                          }
                        >
                          Retry
                        </Button>
                      )}
                    </div>
                  )}
                {missingPackages.length > 0 && (
                  <div className="border-t px-3 py-2 pl-[42px]">
                    <MissingPackagePrompt
                      packages={missingPackages}
                      featureName={`${optionLabel} export`}
                      description={
                        missingPackageFailure?.description ??
                        parquetEligibility?.reason
                      }
                      onInstall={() => {
                        void retryAfterInstall(
                          missingPackageFailure?.action ?? {
                            destination: "download",
                            format: "parquet",
                          },
                        );
                      }}
                      className="items-start"
                    />
                  </div>
                )}
                {rowFailure?.kind === "error" &&
                  missingPackages.length === 0 && (
                    <div className="border-t px-3 py-2 pl-[42px]">
                      <Alert
                        variant="destructive"
                        className="p-3 has-[svg]:pl-9 [&>svg]:left-3 [&>svg]:top-3"
                      >
                        <AlertCircleIcon className="h-4 w-4" />
                        <div>
                          <AlertTitle className="text-sm">
                            {rowFailure.title}
                          </AlertTitle>
                          <AlertDescription className="text-xs">
                            {rowFailure.description}
                          </AlertDescription>
                        </div>
                      </Alert>
                    </div>
                  )}
              </li>
            );
          })}
        </ul>
      </DialogContent>
    </Dialog>
  );
};

interface ExportSettingsFieldsProps {
  format: ConfigurableFormat;
  settings: ExportSettings;
  onChange: React.Dispatch<React.SetStateAction<ExportSettings>>;
}

const ExportSettingsFields: React.FC<ExportSettingsFieldsProps> = ({
  format,
  settings,
  onChange,
}) => {
  const id = React.useId();

  const encodingField = (encoding: Encoding, key: "csv" | "tsv") => (
    <SettingField
      id={`${id}-encoding`}
      label="Encoding"
      help="Text encoding of the saved file. Pick UTF-8 with BOM when Excel shows garbled accents. Copies always use UTF-8."
    >
      <NativeSelect
        id={`${id}-encoding`}
        className="mb-0 w-full"
        value={encoding}
        onChange={(event) => {
          const next = event.target.value as Encoding;
          onChange((current) => ({
            ...current,
            [key]: { ...current[key], encoding: next },
          }));
        }}
      >
        {ENCODINGS.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </NativeSelect>
    </SettingField>
  );

  switch (format) {
    case "csv":
      return (
        <>
          <SettingField
            id={`${id}-separator`}
            label="Delimiter"
            help="Character between fields. Semicolon suits spreadsheets in locales that use a comma as the decimal separator."
          >
            <NativeSelect
              id={`${id}-separator`}
              className="mb-0 w-full"
              value={settings.csv.separator}
              onChange={(event) => {
                const next = event.target.value as Separator;
                onChange((current) => ({
                  ...current,
                  csv: { ...current.csv, separator: next },
                }));
              }}
            >
              {SEPARATORS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </NativeSelect>
          </SettingField>
          {encodingField(settings.csv.encoding, "csv")}
        </>
      );
    case "tsv":
      return encodingField(settings.tsv.encoding, "tsv");
    case "json":
      return (
        <SettingField
          id={`${id}-ensure-ascii`}
          label="Escape non-ASCII"
          help="Write characters outside ASCII as \\u escapes. Turn off to keep accents and symbols readable in the file."
        >
          <Switch
            id={`${id}-ensure-ascii`}
            size="xs"
            checked={settings.json.ensureAscii}
            onCheckedChange={(checked) => {
              onChange((current) => ({
                ...current,
                json: { ensureAscii: checked },
              }));
            }}
          />
        </SettingField>
      );
    default:
      logNever(format);
      return null;
  }
};

interface SettingFieldProps {
  id: string;
  label: string;
  help: string;
  children: React.ReactNode;
}

const SettingField: React.FC<SettingFieldProps> = ({
  id,
  label,
  help,
  children,
}) => (
  <div className="grid gap-1.5">
    <span className="flex items-center gap-1">
      <Label htmlFor={id} className="text-xs font-medium">
        {label}
      </Label>
      <Tooltip content={help}>
        <button
          type="button"
          className="inline-flex text-muted-foreground hover:text-foreground"
          aria-label={`${label} help`}
        >
          <InfoIcon className="h-3 w-3" />
        </button>
      </Tooltip>
    </span>
    <span className="flex items-center">{children}</span>
  </div>
);

function fetchJson(url: string): Promise<Record<string, unknown>[]> {
  return fetchText(url).then(
    jsonParseWithSpecialChar<Record<string, unknown>[]>,
  );
}

function fetchText(url: string): Promise<string> {
  return fetch(url).then((res) => {
    if (!res.ok) {
      throw new Error(res.statusText);
    }
    return res.text();
  });
}
