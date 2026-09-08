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
import { toast } from "@/components/ui/use-toast";
import { Constants } from "@/core/constants";
import { getExportLayout } from "@/core/export/layout";
import { useRequestClient } from "@/core/network/requests";
import { VirtualFileTracker } from "@/core/static/virtual-file-tracker";
import { Spinner } from "../icons/spinner";

/**
 * Where "Publish HTML to web" stages uploads. Overridable for local
 * development and self-hosted deployments; publishing goes through the
 * pending/claim flow, so nothing is public until the user confirms in
 * the tab this opens.
 */
function getPublishBaseUrl(): string {
  return localStorage.getItem("marimo:cloud-base-url") ?? Constants.molab;
}

interface PendingUploadResponse {
  pendingId: string;
  presignedUrl: string;
  claimUrl: string;
  expiresAt: string;
}

/**
 * Stage the HTML with marimo cloud: reserve a pending-upload ticket, PUT the
 * bytes to the presigned URL, and return the claim URL where the user
 * confirms the publish.
 */
async function stageForPublish(
  fileName: string,
  html: string,
): Promise<string> {
  const baseUrl = getPublishBaseUrl();
  const blob = new Blob([html], { type: "text/html" });
  // Keep in sync with marimo-cloud MAX_ARTIFACT_BYTES.
  const maxBytes = 100 * 1024 * 1024;
  if (blob.size > maxBytes) {
    throw new Error("File is too large. Maximum size is 100 MB.");
  }

  const staged = await fetch(`${baseUrl}/api/artifacts/pending`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fileName, fileSize: blob.size }),
  });
  if (!staged.ok) {
    const body = (await staged.json().catch(() => null)) as {
      error?: string;
    } | null;
    throw new Error(
      body?.error ??
        (staged.status === 429
          ? "Too many uploads, try again later"
          : "Failed to prepare the upload"),
    );
  }
  const { presignedUrl, claimUrl } =
    (await staged.json()) as PendingUploadResponse;

  // The presigned PUT is capped to the declared size; the browser sends the
  // matching Content-Length automatically from the blob.
  const put = await fetch(presignedUrl, { method: "PUT", body: blob });
  if (!put.ok) {
    throw new Error("Failed to upload the notebook export");
  }

  return claimUrl;
}

export const ShareStaticNotebookModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [isPublishing, setIsPublishing] = useState(false);
  const { exportAsHTML } = useRequestClient();

  const handlePublish = async () => {
    setIsPublishing(true);
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

      onClose();
      // Popup blockers may swallow window.open after async work, so the
      // toast always carries the link as a fallback.
      window.open(claimUrl, "_blank");
      toast({
        title: "Notebook staged",
        description: (
          <div>
            Finish publishing in the tab that just opened, or{" "}
            <a
              href={claimUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
            >
              open the confirmation page
            </a>
            .
          </div>
        ),
      });
    } catch (error) {
      toast({
        title: "Publish failed",
        description:
          error instanceof Error ? error.message : "Something went wrong",
        variant: "danger",
      });
    } finally {
      setIsPublishing(false);
    }
  };

  return (
    <DialogContent className="sm:max-w-[480px]">
      <DialogHeader>
        <DialogTitle>Publish HTML to web</DialogTitle>
        <DialogDescription>
          Publish a static, non-interactive snapshot of this notebook through{" "}
          <a href={Constants.molab} target="_blank" className="underline">
            molab
          </a>
          . Nothing is public yet: a new tab will open where you sign in, choose
          a name, and confirm the publish.
        </DialogDescription>
      </DialogHeader>
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
              Publish
            </>
          )}
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};
