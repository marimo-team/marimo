/* Copyright 2026 Marimo. All rights reserved. */

import { useMediaQuery } from "@uidotdev/usehooks";
import type React from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { Spinner } from "@/components/icons/spinner";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/utils/cn";
import { FORMAT_DEFINITIONS } from "./format-options";
import { FormatNotice, FormatStatusIcon } from "./format-notice";
import type { ExportFormat } from "./state";
import { useExportDialog } from "./use-export-dialog";

const DESKTOP_LAYOUT_QUERY = "(min-width: 640px)";

export const ExportDialog: React.FC<{
  initialFormat?: ExportFormat;
  onClose: () => void;
  returnFocusRef?: React.RefObject<HTMLElement | null>;
}> = ({ initialFormat, onClose, returnFocusRef }) => {
  const {
    dialogRef,
    isExporting,
    formats,
    options,
    selected,
    selectFormat,
    updateOptions,
    submit,
  } = useExportDialog({ initialFormat, onClose });
  const desktopLayout = useMediaQuery(DESKTOP_LAYOUT_QUERY);
  const {
    format,
    status,
    usesBrowserPrint,
    actionLabel,
    command,
    footerDescription,
  } = selected;
  const definition = FORMAT_DEFINITIONS[format];
  const FormatOptions = definition.Options;

  const returnFocusProps = returnFocusRef
    ? {
        onCloseAutoFocus: (event: Event) => {
          event.preventDefault();
          returnFocusRef.current?.focus();
        },
      }
    : {};

  return (
    <DialogContent
      ref={dialogRef}
      className="grid h-dvh max-h-[760px] min-w-0 w-[calc(100vw-2rem)] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0 sm:top-[5vh] sm:h-[90vh] sm:max-h-[640px] sm:max-w-3xl"
      data-testid="export-dialog"
      {...returnFocusProps}
    >
      <DialogHeader className="border-b px-5 py-4 pr-12">
        <DialogTitle>Export notebook</DialogTitle>
        <DialogDescription>
          Choose a format and adjust its options.
        </DialogDescription>
      </DialogHeader>

      <Tabs
        value={format}
        onValueChange={selectFormat}
        orientation={desktopLayout ? "vertical" : "horizontal"}
        className="flex min-h-0 min-w-0 flex-col overflow-hidden sm:grid sm:grid-cols-[168px_minmax(0,1fr)]"
      >
        <TabsList
          aria-label="Export format"
          className="grid max-h-none shrink-0 grid-cols-2 items-stretch justify-start gap-1 overflow-auto rounded-none border-b bg-muted/20 p-2 min-[360px]:grid-cols-3 sm:flex sm:h-full sm:flex-col sm:border-b-0 sm:border-r"
        >
          {formats.map(({ format: candidate, status: candidateStatus }) => {
            const candidateDefinition = FORMAT_DEFINITIONS[candidate];
            return (
              <TabsTrigger
                key={candidate}
                value={candidate}
                disabled={isExporting}
                className="min-w-0 justify-start gap-2 px-2.5 py-2 text-xs data-[state=active]:shadow-xs sm:w-full sm:text-sm"
                data-testid={`export-format-${candidate}`}
              >
                <candidateDefinition.Icon
                  className="size-3.5 shrink-0"
                  strokeWidth={1.5}
                />
                <span className="truncate">{candidateDefinition.label}</span>
                <FormatStatusIcon status={candidateStatus} />
              </TabsTrigger>
            );
          })}
        </TabsList>

        <TabsContent
          value={format}
          className="mt-0 min-h-0 min-w-0 overflow-y-auto px-4 py-3"
        >
          <div className="mb-3">
            <h3 className="text-base font-semibold">{definition.label}</h3>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {definition.description}
            </p>
          </div>

          <FormatNotice
            format={format}
            formatLabel={definition.label}
            status={status}
          />

          {usesBrowserPrint ? null : (
            <FormatOptions
              options={options}
              updateOptions={updateOptions}
              disabled={isExporting}
            />
          )}
        </TabsContent>
      </Tabs>

      <footer className="min-w-0 border-t bg-muted/20 px-4 py-3">
        {command ? (
          <div className="flex min-w-0 items-center gap-2 rounded-md border bg-background px-2.5 py-2 font-mono text-xs">
            <span
              className="select-none text-muted-foreground"
              aria-hidden={true}
            >
              $
            </span>
            <code
              className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap"
              data-testid="export-cli-command"
              aria-label="Equivalent POSIX shell command"
            >
              {command}
            </code>
            <CopyClipboardIcon
              value={command}
              className="size-3.5"
              buttonClassName={cn(
                buttonVariants({ variant: "ghost", size: "icon" }),
                "shrink-0",
              )}
              tooltip="Copy POSIX shell command"
              ariaLabel="Copy POSIX shell command"
              toastTitle="Command copied"
            />
          </div>
        ) : null}

        <div
          className={cn(
            "flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
            command && "mt-3",
          )}
        >
          {footerDescription ? (
            <p className="text-xs text-muted-foreground">{footerDescription}</p>
          ) : null}
          <Button
            type="button"
            disabled={!status.available || isExporting}
            aria-busy={isExporting}
            onClick={submit}
            className={cn(
              "border-(--blue-11) bg-(--blue-11) hover:border-(--blue-12) hover:bg-(--blue-12) sm:min-w-36 dark:border-(--blue-7) dark:bg-(--blue-5) dark:text-(--blue-12) dark:hover:border-(--blue-8) dark:hover:bg-(--blue-6)",
              !footerDescription && "sm:ml-auto",
            )}
            data-testid="export-submit"
          >
            {isExporting && (
              <Spinner size="small" className="mr-2" aria-hidden={true} />
            )}
            {usesBrowserPrint ? "Print to PDF" : actionLabel}
          </Button>
        </div>
      </footer>
    </DialogContent>
  );
};
