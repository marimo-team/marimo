/* Copyright 2024 Marimo. All rights reserved. */

import { CopyIcon } from "lucide-react";
import React, { useMemo, useState } from "react";
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
import { exportAsHTML } from "@/core/network/requests";
import { VirtualFileTracker } from "@/core/static/virtual-file-tracker";
import { copyToClipboard } from "@/utils/copy";
import { Events } from "@/utils/events";
import { Input } from "../ui/input";
import { Tooltip } from "../ui/tooltip";

const BASE_URL = "https://static.marimo.app";

export const ShareStaticNotebookModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [slug, setSlug] = useState("");
  // 4 character random string
  const randomHash = useMemo(() => Math.random().toString(36).slice(2, 6), []);

  // Globally unique path
  const path = `${slug}-${randomHash}`;
  const url = `${BASE_URL}/static/${path}`;

  return (
    <DialogContent className="w-fit">
      <form
        onSubmit={async (e) => {
          e.preventDefault();

          onClose();
          const html = await exportAsHTML({
            download: false,
            includeCode: true,
            files: VirtualFileTracker.INSTANCE.filenames(),
          });

          const prevToast = toast({
            title: "Uploading static notebook...",
            description: "Please wait.",
          });

          await fetch(`${BASE_URL}/api/static`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              html: html,
              path: path,
            }),
          }).catch(() => {
            prevToast.dismiss();
            toast({
              title: "Error uploading static page",
              description: (
                <div>
                  Please try again later. If the problem persists, please file a
                  bug report on{" "}
                  <a
                    href={Constants.issuesPage}
                    target="_blank"
                    className="underline"
                  >
                    GitHub
                  </a>
                  .
                </div>
              ),
            });
          });

          prevToast.dismiss();
          toast({
            title: "Static page uploaded!",
            description: (
              <div>
                The URL has been copied to your clipboard.
                <br />
                You can share it with anyone.
              </div>
            ),
          });
        }}
      >
        <DialogHeader>
          <DialogTitle>Share static notebook</DialogTitle>
          <DialogDescription>
            You can publish a static, non-interactive version of this notebook
            to the public web. We will create a link for you that lives on{" "}
            <a href={BASE_URL} target="_blank">
              {BASE_URL}
            </a>
            .
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-6 py-4">
          <Input
            data-testid="slug-input"
            id="slug"
            autoFocus={true}
            value={slug}
            placeholder="Notebook slug"
            onChange={(e) => {
              const newSlug = e.target.value
                .toLowerCase()
                .replaceAll(/\s/g, "-")
                .replaceAll(/[^\da-z-]/g, "");
              setSlug(newSlug);
            }}
            required={true}
            autoComplete="off"
          />

          <div className="font-semibold text-sm text-muted-foreground gap-2 flex flex-col">
            Anyone will be able to access your notebook at this URL:
            <div className="flex items-center gap-2">
              <CopyButton text={url} />
              <span className="text-primary">{url}</span>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button
            data-testid="cancel-share-static-notebook-button"
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            data-testid="share-static-notebook-button"
            aria-label="Save"
            variant="default"
            type="submit"
            onClick={async () => {
              await copyToClipboard(url);
            }}
          >
            Create
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};

const CopyButton = (props: { text: string }) => {
  const [copied, setCopied] = React.useState(false);

  const copy = Events.stopPropagation(async (e) => {
    e.preventDefault();
    await copyToClipboard(props.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  });

  return (
    <Tooltip content="Copied!" open={copied}>
      <Button
        data-testid="copy-static-notebook-url-button"
        onClick={copy}
        size="xs"
        variant="secondary"
      >
        <CopyIcon size={14} strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};
