/* Copyright 2023 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  DialogFooter,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Slot } from "@radix-ui/react-slot";
import React, { PropsWithChildren, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { Input } from "../ui/input";
import { CopyIcon } from "lucide-react";
import { Events } from "@/utils/events";
import { Tooltip } from "../ui/tooltip";
import { createStaticHTMLNotebook } from "@/core/static/download-html";
import { Constants } from "@/core/constants";

export const ShareStaticNotebookButton: React.FC<PropsWithChildren> = ({
  children,
}) => {
  const { openModal, closeModal } = useImperativeModal();

  return (
    <Slot
      onClick={() =>
        openModal(<ShareStaticNotebookModal onClose={closeModal} />)
      }
    >
      {children}
    </Slot>
  );
};

export const ShareStaticNotebookModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [slug, setSlug] = useState("");
  // 4 character random string
  const randomHash = useRef(Math.random().toString(36).slice(2, 6)).current;

  const path = `${slug}-${randomHash}`;
  const url = `https://marimo.io/static/${path}`;

  return (
    <DialogContent className="w-fit">
      <form
        onSubmit={async (e) => {
          e.preventDefault();

          onClose();
          const html = await createStaticHTMLNotebook();

          const prevToast = toast({
            title: "Uploading static notebook...",
            description: "Please wait.",
          });

          await fetch("https://marimo.io/api/static", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              html: html,
              path: path,
            }),
          }).catch(() => {
            prevToast.update({
              title: "Error uploading static page",
              description: (
                <div>
                  Please try again later. If the problem persists, please file a
                  bug report on{" "}
                  <a
                    href={Constants.issuesPage}
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    GitHub
                  </a>
                  .
                </div>
              ),
            });
          });

          prevToast.update({
            title: "Static page uploaded!",
            description: (
              <div>
                You can access the page at{" "}
                <a href={url} target="_blank" rel="noreferrer">
                  {url}
                </a>
              </div>
            ),
          });
        }}
      >
        <DialogHeader>
          <DialogTitle>Share static notebook</DialogTitle>
          <DialogDescription>
            You can share a static, non-interactive version of this notebook. We
            will create a link for you that lives on{" "}
            <a href="https://marimo.io" target="_blank" rel="noreferrer">
              https://marimo.io
            </a>
            .
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-6 py-4">
          <Input
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
            You will be able to access your notebook at this URL:
            <div className="flex items-center gap-2">
              <CopyButton text={url} />
              <span className="text-primary">{url}</span>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            aria-label="Save"
            variant="default"
            type="submit"
            onClick={() => {
              navigator.clipboard.writeText(url);
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

  const copy = Events.stopPropagation((e) => {
    e.preventDefault();
    navigator.clipboard.writeText(props.text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  });

  return (
    <Tooltip content="Copied!" open={copied}>
      <Button onClick={copy} size="xs" variant="secondary">
        <CopyIcon size={14} strokeWidth={1.5} />
      </Button>
    </Tooltip>
  );
};
