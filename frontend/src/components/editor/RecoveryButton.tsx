/* Copyright 2024 Marimo. All rights reserved. */
import { Button as EditorButton } from "@/components/editor/inputs/Inputs";
import { Button } from "components/ui/button";
import { useHotkey } from "../../hooks/useHotkey";
import { SaveIcon } from "lucide-react";
import { Tooltip } from "../ui/tooltip";
import { renderShortcut } from "../shortcuts/renderShortcut";
import { useImperativeModal } from "../modal/ImperativeModal";
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
} from "../ui/dialog";
import { downloadBlob } from "@/utils/download";

const RecoveryModal = (props: {
  proposedName: string;
  getCellsAsJSON: () => string;
  closeModal: () => void;
}): JSX.Element => {
  const downloadRecoveryFile = () => {
    downloadBlob(
      new Blob([props.getCellsAsJSON()], { type: "text/plain" }),
      `${props.proposedName}.json`,
    );
  };

  // NB: we use markdown class to have sane styling for list, paragraph
  return (
    <DialogContent className="w-fit">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          downloadRecoveryFile();
          props.closeModal();
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            props.closeModal();
          }
        }}
      >
        <DialogTitle className="text-accent mb-6">
          Download unsaved changes?
        </DialogTitle>
        <DialogDescription className="markdown">
          <p>This app has unsaved changes. To recover:</p>

          <ol>
            <li style={{ paddingBottom: "10px" }}>
              Click the "Download" button. This will download a file
              called&nbsp;
              <code>{props.proposedName}.json</code>. This file contains your
              code.
            </li>

            <li style={{ paddingBottom: "10px" }}>
              In your terminal, type
              <code style={{ display: "block", padding: "10px" }}>
                marimo recover {props.proposedName}.json {">"}{" "}
                {props.proposedName}.py
              </code>
              to overwrite <code>{props.proposedName}.py</code> with the
              recovered changes.
            </li>
          </ol>
        </DialogDescription>
        <DialogFooter>
          <Button
            aria-label="Cancel"
            variant="secondary"
            data-testid="cancel-recovery-button"
            onClick={props.closeModal}
          >
            Cancel
          </Button>
          <Button
            data-testid="download-recovery-button"
            aria-label="Download"
            variant="default"
            type="submit"
          >
            Download
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};

export const RecoveryButton = (props: {
  filename: string | null;
  needsSave: boolean;
  getCellsAsJSON: () => string;
}): JSX.Element => {
  const { filename, needsSave, getCellsAsJSON } = props;
  const { openModal, closeModal } = useImperativeModal();

  const proposedName = filename === null ? "app" : filename.slice(0, -3);

  const openRecoveryModal = () => {
    if (needsSave) {
      openModal(
        <RecoveryModal
          getCellsAsJSON={getCellsAsJSON}
          proposedName={proposedName}
          closeModal={closeModal}
        />,
      );
    }
  };

  useHotkey("global.save", openRecoveryModal);

  return (
    <Tooltip content={renderShortcut("global.save")}>
      <EditorButton
        onClick={openRecoveryModal}
        id="save-button"
        aria-label="Save"
        className="rectangle"
        color={needsSave ? "yellow" : "gray"}
      >
        <SaveIcon strokeWidth={1.5} />
      </EditorButton>
    </Tooltip>
  );
};
