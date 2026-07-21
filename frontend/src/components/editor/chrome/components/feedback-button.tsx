/* Copyright 2026 Marimo. All rights reserved. */

import { Slot as SlotPrimitive } from "radix-ui";

const Slot = SlotPrimitive.Slot;

import { useAtomValue } from "jotai";
import { CheckIcon, ExternalLinkIcon, TriangleAlertIcon } from "lucide-react";
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
import { toast } from "@/components/ui/use-toast";
import { notebookAtom } from "@/core/cells/cells";
import { Constants } from "@/core/constants";
import {
  buildIssueDetails,
  createPartialEnvironment,
  type EnvironmentDiagnostics,
  enrichEnvironment,
  type NotebookSource,
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
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";

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

  const [includeNotebook, setIncludeNotebook] = useState(false);

  const notebookSourceReason = notebookSourceAvailable
    ? undefined
    : filename === null
      ? "Save the notebook first."
      : !codeAvailable
        ? "Notebook source is hidden in this view."
        : "Connect the notebook to include its source.";

  const notebookSourceRequest = useAsyncData(async () => {
    if (!includeNotebook || !notebookSourceAvailable || filename === null) {
      return undefined;
    }
    const { contents } = await readCode();
    return { filename, contents } satisfies NotebookSource;
  }, [includeNotebook, notebookSourceAvailable, filename, readCode]);

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

  const [issueDetailsCopied, setIssueDetailsCopied] = useState(false);

  const copyIssueDetails = async () => {
    if (!environment) {
      return;
    }
    const notebookForReport = includeNotebook
      ? notebookSourceRequest.data
      : undefined;
    await copyToClipboard(
      buildIssueDetails({ environment, errors, notebook: notebookForReport }),
    );
    setIssueDetailsCopied(true);
    setTimeout(() => setIssueDetailsCopied(false), 2000);
    toast({
      title:
        environmentRequest.status === "error"
          ? "Partial issue details copied"
          : "Issue details copied",
    });
  };

  return (
    <DialogContent className="w-[540px] max-w-[90vw]">
      <DialogHeader>
        <DialogTitle>Report an issue</DialogTitle>
        <DialogDescription>
          Copy your environment and any current errors to include in a GitHub
          bug report. Nothing is uploaded automatically; review the details
          before posting.
        </DialogDescription>
      </DialogHeader>

      <div className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="default"
            disabled={
              !environment ||
              (includeNotebook && notebookSourceRequest.isFetching)
            }
            onClick={copyIssueDetails}
          >
            {issueDetailsCopied && (
              <CheckIcon className="w-4 h-4 mr-2 text-(--grass-11)" />
            )}
            {issueDetailsCopied ? "Copied!" : "Copy issue details"}
          </Button>
          <Button type="button" variant="outline" asChild={true}>
            <a href={Constants.bugReportUrl} target="_blank" rel="noreferrer">
              <ExternalLinkIcon className="w-4 h-4 mr-2" />
              Open GitHub issue
            </a>
          </Button>
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
            <span className="text-sm font-medium">Current errors</span>
            <CollapsiblePreview
              content={errors.map(formatCellError).join("\n\n---\n\n")}
            />
          </div>
        )}

        {environment && errors.length === 0 && (
          <span className="text-sm text-muted-foreground">
            No current errors detected.
          </span>
        )}

        <div className="flex flex-col gap-1">
          <div className="flex items-start gap-2 text-sm">
            <Checkbox
              id="issue-include-notebook"
              className="mt-0.5"
              checked={includeNotebook}
              disabled={!notebookSourceAvailable}
              onCheckedChange={(checked) =>
                setIncludeNotebook(checked === true)
              }
              aria-label="Include full notebook source"
            />
            <label htmlFor="issue-include-notebook">
              Include full notebook source
            </label>
          </div>
          <p className="text-xs text-muted-foreground ml-6">
            Copies the entire saved Python source, including comments, literal
            data, embedded credentials, and package metadata. Outputs and
            external files are not included. Review it before posting.{" "}
            <span className="font-bold">
              For private notebooks, paste a minimal reproduction instead.
            </span>
          </p>
          {notebookSourceReason && (
            <span className="text-xs text-muted-foreground ml-6">
              {notebookSourceReason}
            </span>
          )}
          {includeNotebook && notebookSourceRequest.status === "error" && (
            <span className="text-xs text-(--red-11) ml-6">
              Notebook source could not be loaded.
            </span>
          )}
        </div>

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
