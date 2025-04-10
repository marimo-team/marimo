/* Copyright 2024 Marimo. All rights reserved. */
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  DialogFooter,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Slot } from "@radix-ui/react-slot";
import React, { type PropsWithChildren } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/use-toast";
import { Constants } from "@/core/constants";
import { Input } from "@/components/ui/input";
import { EditorView } from "@codemirror/view";
import { useState } from "react";
import { useTheme } from "@/theme/useTheme";
import { LazyAnyLanguageCodeMirror } from "@/plugins/impl/code/LazyAnyLanguageCodeMirror";

export const ContributeSnippetButton: React.FC<PropsWithChildren> = ({
  children,
}) => {
  const { openModal, closeModal } = useImperativeModal();

  return (
    <Slot
      onClick={() => openModal(<ContributeSnippetModal onClose={closeModal} />)}
    >
      {children}
    </Slot>
  );
};

const extensions = [EditorView.lineWrapping];

const ContributeSnippetModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [code, setCode] = useState("");
  const { theme } = useTheme();

  return (
    <DialogContent className="w-fit">
      <form
        onSubmit={async (e) => {
          e.preventDefault();

          const formData = new FormData(e.target as HTMLFormElement);
          const title = formData.get("title");
          const description = formData.get("description");
          const code = formData.get("code");

          // Fire-and-forget we don't care about the response
          void fetch("https://marimo.io/api/suggest-snippet", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              title,
              description,
              code,
            }),
          });
          onClose();
          toast({
            title: "Snippet Submitted",
            description:
              "Thank you for contributing! We will review your snippet shortly.",
          });
        }}
      >
        <DialogHeader>
          <DialogTitle>Contribute a Snippet</DialogTitle>
          <DialogDescription>
            Have a useful snippet you want to share with the community? Submit
            it here or make a pull request{" "}
            <a
              href={Constants.githubPage}
              target="_blank"
              className="underline"
            >
              on GitHub
            </a>
            .
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-6 py-4">
          <Input
            id="title"
            name="title"
            autoFocus={true}
            placeholder="Title"
            required={true}
            autoComplete="off"
          />
          <Textarea
            id="description"
            name="description"
            autoFocus={true}
            placeholder="Description"
            rows={5}
            required={true}
            autoComplete="off"
          />
          <input type="hidden" name="code" value={code} />
          <LazyAnyLanguageCodeMirror
            theme={theme === "dark" ? "dark" : "light"}
            language="python"
            className="cm border rounded overflow-hidden"
            extensions={extensions}
            value={code}
            onChange={setCode}
          />
        </div>
        <DialogFooter>
          <Button
            data-testid="snippet-cancel-button"
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            data-testid="snippet-send-button"
            aria-label="Save"
            variant="default"
            type="submit"
          >
            Send
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};
