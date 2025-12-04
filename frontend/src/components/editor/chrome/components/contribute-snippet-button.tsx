/* Copyright 2024 Marimo. All rights reserved. */

import { Slot } from "@radix-ui/react-slot";
import React, { type PropsWithChildren } from "react";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { Button } from "@/components/ui/button";
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Constants } from "@/core/constants";

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

const ContributeSnippetModal: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  return (
    <DialogContent className="max-w-md">
      <DialogHeader>
        <DialogTitle>Contribute a Snippet</DialogTitle>
        <DialogDescription>
          Have a useful snippet you want to share with the community? Make a
          pull request{" "}
          <a href={Constants.githubPage} target="_blank" className="underline">
            on GitHub
          </a>
          .
        </DialogDescription>
      </DialogHeader>
      <DialogFooter>
        <Button
          data-testid="snippet-close-button"
          variant="default"
          onClick={onClose}
        >
          Close
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};
