/* Copyright 2026 Marimo. All rights reserved. */

import { Slot as SlotPrimitive } from "radix-ui";

const Slot = SlotPrimitive.Slot;

import { useAtomValue } from "jotai";
import { ExternalLinkIcon, TriangleAlertIcon } from "lucide-react";
import React, { type PropsWithChildren, useMemo, useState } from "react";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { notebookAtom } from "@/core/cells/cells";
import { Constants } from "@/core/constants";
import {
  buildBugReportUrl,
  createPartialEnvironment,
  type EnvironmentDiagnostics,
  enrichEnvironment,
  formatCodeSection,
  formatEnvironmentSection,
  formatErrorsSection,
} from "@/core/diagnostics/issue-details";
import {
  formatCellError,
  getCellErrorEntries,
} from "@/core/errors/error-entries";
import { useNotebookCodeAvailable } from "@/core/meta/code-visibility";
import { getMarimoVersion } from "@/core/meta/globals";
import { connectionAtom } from "@/core/network/connection";
import { useRequestClient } from "@/core/network/requests";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useLocalStorage } from "@/hooks/useLocalStorage";
import { cn } from "@/utils/cn";

const CollapsiblePreview: React.FC<{ content: string }> = ({ content }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="flex flex-col gap-1">
      <div className="relative">
        <pre
          className={cn(
            "text-xs bg-muted rounded p-2 overflow-x-auto whitespace-pre-wrap",
            !expanded && "max-h-24 overflow-hidden",
          )}
        >
          {content}
        </pre>
        {!expanded && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 rounded-b bg-gradient-to-b from-transparent to-muted" />
        )}
      </div>
      <Button
        type="button"
        variant="link"
        size="xs"
        className="self-start"
        onClick={() => setExpanded((value) => !value)}
      >
        {expanded ? "Show less" : "Show more"}
      </Button>
    </div>
  );
};

export const FeedbackButton: React.FC<PropsWithChildren> = ({ children }) => {
  const { openModal, closeModal } = useImperativeModal();

  return (
    <Slot onClick={() => openModal(<FeedbackModal onClose={closeModal} />)}>
      {children}
    </Slot>
  );
};

export const FeedbackModal: React.FC<{
  onClose: () => void;
}> = () => {
  const { getEnvironmentInfo, readCode } = useRequestClient();
  const environmentRequest = useAsyncData(
    async () => getEnvironmentInfo(),
    [getEnvironmentInfo],
  );

  const notebook = useAtomValue(notebookAtom);
  // biome-ignore lint/correctness/useExhaustiveDependencies: recompute when the notebook changes
  const errors = useMemo(() => getCellErrorEntries(store), [notebook]);

  const cells = notebook.cellIds.inOrderIds.map(
    (cellId) => notebook.cellData[cellId],
  );
  const codeAvailable = useNotebookCodeAvailable(cells);
  const filename = useAtomValue(filenameAtom);
  const connection = useAtomValue(connectionAtom);
  const notebookSourceAvailable =
    filename !== null &&
    codeAvailable &&
    connection.state === WebSocketState.OPEN;

  const notebookSourceReason = notebookSourceAvailable
    ? undefined
    : filename === null
      ? "Save the notebook first."
      : !codeAvailable
        ? "Notebook source is hidden in this view."
        : "Connect the notebook to include its source.";

  const [includeErrors, setIncludeErrors] = useLocalStorage(
    "marimo:issue-report:include-errors",
    false,
  );
  const [includeCode, setIncludeCode] = useLocalStorage(
    "marimo:issue-report:include-code",
    false,
  );

  const environment: EnvironmentDiagnostics | undefined =
    environmentRequest.data
      ? enrichEnvironment(environmentRequest.data, navigator.userAgent)
      : environmentRequest.status === "error"
        ? createPartialEnvironment(
            getMarimoVersion(),
            navigator.userAgent,
            navigator.language,
            "Server environment information unavailable",
          )
        : undefined;

  const codeRequest = useAsyncData(async () => {
    if (!includeCode || !notebookSourceAvailable) {
      return undefined;
    }
    const { contents } = await readCode();
    return contents;
  }, [includeCode, notebookSourceAvailable, readCode]);

  const { url: githubIssueUrl, omitted } = useMemo(() => {
    if (!environment) {
      return { url: Constants.bugReportUrl, omitted: [] as string[] };
    }
    const fields: Record<string, string> = {
      env: formatEnvironmentSection(environment),
    };
    if (includeErrors && errors.length > 0) {
      fields["bug-description"] = formatErrorsSection(errors);
    }
    if (includeCode && codeRequest.data) {
      fields["reproduction-code"] = formatCodeSection(codeRequest.data);
    }
    return buildBugReportUrl(Constants.bugReportUrl, fields);
  }, [environment, errors, includeErrors, includeCode, codeRequest.data]);

  const omittedLabels = omitted
    .map((field) =>
      field === "bug-description"
        ? "errors"
        : field === "reproduction-code"
          ? "code"
          : field,
    )
    .join(", ");

  return (
    <DialogContent className="w-[540px] max-w-[90vw]">
      <DialogHeader>
        <DialogTitle>Report an issue</DialogTitle>
        <DialogDescription>
          Open a GitHub bug report prefilled with your environment, and
          optionally your current errors and notebook code. Nothing is uploaded
          automatically; review the details before posting.
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
        <div className="flex flex-col gap-3">
          <Button
            type="button"
            variant="default"
            size="xs"
            asChild={true}
            className="self-start"
          >
            <a href={githubIssueUrl} target="_blank" rel="noreferrer">
              <ExternalLinkIcon className="w-4 h-4 mr-2" />
              Open GitHub issue
            </a>
          </Button>

          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2 text-sm">
              <Checkbox
                id="issue-include-errors"
                checked={includeErrors}
                disabled={errors.length === 0}
                onCheckedChange={(checked) =>
                  setIncludeErrors(checked === true)
                }
                aria-label="Include errors"
              />
              <label htmlFor="issue-include-errors">Include errors</label>
            </div>

            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 text-sm">
                <Checkbox
                  id="issue-include-code"
                  checked={includeCode}
                  disabled={!notebookSourceAvailable}
                  onCheckedChange={(checked) =>
                    setIncludeCode(checked === true)
                  }
                  aria-label="Include notebook code"
                />
                <label htmlFor="issue-include-code">
                  Include notebook code
                </label>
              </div>
              {notebookSourceReason && (
                <span className="text-xs text-muted-foreground ml-6">
                  {notebookSourceReason}
                </span>
              )}
              {includeCode && codeRequest.status === "error" && (
                <span className="text-xs text-(--red-11) ml-6">
                  Notebook source could not be loaded.
                </span>
              )}
            </div>
          </div>

          {omittedLabels ? (
            <div className="flex items-start gap-2 text-xs text-(--yellow-11)">
              <TriangleAlertIcon className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>
                Too large to prefill and left out of the link: {omittedLabels}.
                Paste them into the issue manually.
              </span>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              Your environment is always included.
            </p>
          )}
        </div>

        {environmentRequest.status === "pending" && (
          <div className="flex flex-col gap-2">
            <span className="text-sm text-muted-foreground">
              Loading environment details…
            </span>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        )}

        {environmentRequest.status === "error" && (
          <div className="flex items-center gap-2 text-sm">
            <TriangleAlertIcon className="w-4 h-4 text-(--yellow-11) shrink-0" />
            <span>Server environment information unavailable</span>
            <Button
              type="button"
              variant="link"
              size="xs"
              onClick={() => environmentRequest.refetch()}
            >
              Retry
            </Button>
          </div>
        )}

        {environment && (
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Environment details</span>
              <CopyClipboardIcon
                className="w-3.5 h-3.5"
                value={JSON.stringify(environment, null, 2)}
                ariaLabel="Copy environment JSON"
                toastTitle="Environment details copied"
              />
            </div>
            <CollapsiblePreview
              content={JSON.stringify(environment, null, 2)}
            />
          </div>
        )}

        {environment && errors.length > 0 && (
          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Errors</span>
              <CopyClipboardIcon
                className="w-3.5 h-3.5"
                value={formatErrorsSection(errors)}
                ariaLabel="Copy errors"
                toastTitle="Errors copied"
              />
            </div>
            <CollapsiblePreview
              content={errors.map(formatCellError).join("\n\n---\n\n")}
            />
          </div>
        )}

        {environment && errors.length === 0 && (
          <span className="text-sm text-muted-foreground">
            No errors detected.
          </span>
        )}

        <div className="border-t pt-3">
          <p className="text-sm text-muted-foreground">
            Other feedback? Take our{" "}
            <a
              href={Constants.feedbackForm}
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              two-minute survey
            </a>{" "}
            or chat with us on{" "}
            <a
              href={Constants.discordLink}
              target="_blank"
              rel="noreferrer"
              className="underline"
            >
              Discord
            </a>
            .
          </p>
        </div>
      </div>
    </DialogContent>
  );
};
