/* Copyright 2026 Marimo. All rights reserved. */

import { ExternalLinkIcon } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Constants } from "@/core/constants";
import { getExportLayout } from "@/core/export/layout";
import { useRequestClient } from "@/core/network/requests";
import { VirtualFileTracker } from "@/core/static/virtual-file-tracker";
import { Spinner } from "../icons/spinner";
import { stageForPublish } from "./stage-for-publish";

type PublishState =
  | { kind: "idle" }
  | { kind: "publishing" }
  | { kind: "staged"; claimUrl: string }
  | { kind: "failed"; message: string };

export const ShareStaticNotebookModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [state, setState] = useState<PublishState>({ kind: "idle" });
  const { exportAsHTML } = useRequestClient();

  const handlePublish = async () => {
    setState({ kind: "publishing" });
    try {
      const { contents: html, filename } = await exportAsHTML({
        download: false,
        includeCode: true,
        files: VirtualFileTracker.INSTANCE.filenames(),
        layout: await getExportLayout(),
        // Published notebooks are served from a remote origin, so assets must
        // come from the CDN — never the local server (which is the dev-mode
        // default). The server substitutes {version}.
        assetUrl:
          "https://cdn.jsdelivr.net/npm/@marimo-team/frontend@{version}/dist",
      });

      const claimUrl = await stageForPublish(filename, html);

      // Best effort: after the async work above, browsers may treat this as a
      // popup and block it. The dialog keeps the link either way.
      window.open(claimUrl, "_blank", "noopener,noreferrer");
      setState({ kind: "staged", claimUrl });
    } catch (error) {
      setState({
        kind: "failed",
        message:
          error instanceof Error ? error.message : "Something went wrong",
      });
    }
  };

  if (state.kind === "staged") {
    return (
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle>Finish publishing</DialogTitle>
          <DialogDescription>
            We opened the confirmation page in a new tab. If it didn't appear,
            open it below.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            data-testid="done-share-static-notebook-button"
            variant="secondary"
            onClick={onClose}
          >
            Done
          </Button>
          <Button asChild={true} variant="default">
            <a
              data-testid="open-claim-page-link"
              href={state.claimUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLinkIcon size={14} strokeWidth={1.5} className="mr-2" />
              Open confirmation page
            </a>
          </Button>
        </DialogFooter>
      </DialogContent>
    );
  }

  const isPublishing = state.kind === "publishing";

  return (
    <DialogContent className="sm:max-w-[480px]">
      <DialogHeader>
        <DialogTitle>Publish HTML to web</DialogTitle>
        <DialogDescription>
          Publish a static, non-interactive snapshot of this notebook through{" "}
          <a
            href={Constants.molab}
            target="_blank"
            rel="noopener noreferrer"
            className="underline"
          >
            molab
          </a>
          . A new tab will open where you sign in, choose a name, and confirm
          the publish.
        </DialogDescription>
      </DialogHeader>
      {state.kind === "failed" && (
        <p
          role="alert"
          className="text-sm text-destructive"
          data-testid="share-static-notebook-error"
        >
          Publish failed: {state.message}
        </p>
      )}
      <DialogFooter>
        <Button
          data-testid="cancel-share-static-notebook-button"
          variant="secondary"
          onClick={onClose}
          disabled={isPublishing}
        >
          Cancel
        </Button>
        <Button
          data-testid="share-static-notebook-button"
          variant="default"
          disabled={isPublishing}
          onClick={handlePublish}
        >
          {isPublishing ? (
            <>
              <Spinner className="mr-2" size="small" />
              Staging notebook...
            </>
          ) : (
            <>
              <ExternalLinkIcon size={14} strokeWidth={1.5} className="mr-2" />
              {state.kind === "failed" ? "Try again" : "Publish"}
            </>
          )}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};
