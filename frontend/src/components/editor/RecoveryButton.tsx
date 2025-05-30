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
import { useEvent } from "@/hooks/useEvent";
import { getNotebook } from "@/core/cells/cells";
import { notebookCells } from "@/core/cells/utils";
import { useFilename } from "@/core/saving/filename";
import type { Notebook } from "@marimo-team/marimo-api";
import { getMarimoVersion } from "@/core/meta/globals";

const RecoveryModal = (props: {
  proposedName: string;
  closeModal: () => void;
}): JSX.Element => {
  const filename = useFilename();

  const downloadRecoveryFile = () => {
    downloadBlob(
      new Blob([getNotebookJSON()], { type: "text/plain" }),
      `${props.proposedName}.json`,
    );
  };

  const getNotebookJSON = useEvent(() => {
    const notebook = getNotebook();
    const cells = notebookCells(notebook);
    const notbook: Notebook["NotebookV1"] = {
      // filename: filename,
      version: "1",
      metadata: {
        marimo_version: getMarimoVersion(),
      },
      cells: cells.map((cell) => {
        return {
          id: cell.id,
          name: cell.name,
          code: cell.code,
          config: {
            column: 0,
            ...cell.config,
          },
        };
      }),
    };
    return JSON.stringify(notbook, null, 2);
  });

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
        <DialogTitle className="text-accent-foreground mb-6">
          Download unsaved changes?
        </DialogTitle>
        <DialogDescription
          className="markdown break-words"
          style={{ wordBreak: "break-word" }}
        >
          <div className="prose dark:prose-invert">
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
          </div>
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
}): JSX.Element => {
  const { filename, needsSave } = props;
  const { openModal, closeModal } = useImperativeModal();

  const proposedName = filename === null ? "app" : filename.slice(0, -3);

  const openRecoveryModal = () => {
    if (needsSave) {
      openModal(
        <RecoveryModal proposedName={proposedName} closeModal={closeModal} />,
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
        <SaveIcon strokeWidth={1.5} size={18} />
      </EditorButton>
    </Tooltip>
  );
};
