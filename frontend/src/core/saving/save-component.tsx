/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue, useStore } from "jotai";
import { SaveIcon } from "lucide-react";
import { useState } from "react";
import { FilenameInput } from "@/components/editor/header/filename-input";
import { Button as ControlButton } from "@/components/editor/inputs/Inputs";
import { RecoveryButton } from "@/components/editor/RecoveryButton";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { Tooltip } from "@/components/ui/tooltip";
import { useEventListener } from "@/hooks/useEventListener";
import { useHotkey } from "@/hooks/useHotkey";
import { useImperativeModal } from "../../components/modal/ImperativeModal";
import { Button } from "../../components/ui/button";
import {
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "../../components/ui/dialog";
import { Label } from "../../components/ui/label";
import { useEvent } from "../../hooks/useEvent";
import { Logger } from "../../utils/Logger";
import { toast } from "@/components/ui/use-toast";
import { getNotebook } from "../cells/cells";
import { notebookCells } from "../cells/utils";
import { formatAll } from "../codemirror/format";
import { autoSaveConfigAtom } from "../config/config";
import { useAutoExport } from "../export/hooks";
import { getSerializedLayout } from "../layout/layout";
import { layoutStateAtom } from "../layout/state";
import { connectionAtom } from "../network/connection";
import { canEditAtom } from "@/core/notebook";
import { useRequestClient } from "../network/requests";
import { ConnectionState } from "../session/types";
import { filenameAtom } from "./file-state";
import { useFilename, useUpdateFilename } from "./filename";
import { useNotebookDocumentSave } from "./document";
import { documentVersionAtom, needsSaveAtom, savedLayoutAtom } from "./state";
import { useAutoSave } from "./useAutoSave";

let notebookSaveQueue: Promise<void> = Promise.resolve();

export function enqueueNotebookSave<T>(save: () => Promise<T>): Promise<T> {
  const result = notebookSaveQueue.then(save);
  notebookSaveQueue = result.then(
    () => undefined,
    () => undefined,
  );
  return result;
}

export const SaveComponent = () => {
  const filename = useFilename();
  const needsSave = useAtomValue(needsSaveAtom);
  const closed = useAtomValue(connectionAtom).state === ConnectionState.CLOSED;
  const { saveOrNameNotebook, saveIfNotebookIsPersistent } = useSaveNotebook();
  useAutoSaveNotebook({ onSave: saveIfNotebookIsPersistent });

  useAutoExport();

  // Add beforeunload event listener to prevent accidental closing when there are unsaved changes
  useEventListener(window, "beforeunload", (event) => {
    // Only prevent unload if we have unsaved changes
    if (needsSave) {
      // Standard way to show a confirmation dialog before closing
      event.preventDefault();
      // Required for older browsers
      event.returnValue =
        "You have unsaved changes. Are you sure you want to leave?";
      return event.returnValue;
    }
  });

  const handleSaveClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    e.stopPropagation();
    saveOrNameNotebook();
  };

  useHotkey("global.save", saveOrNameNotebook);

  if (closed) {
    return <RecoveryButton filename={filename} needsSave={needsSave} />;
  }

  return (
    <Tooltip content={renderShortcut("global.save")}>
      <ControlButton
        data-testid="save-button"
        id="save-button"
        shape="rectangle"
        color={needsSave ? "yellow" : "hint-green"}
        onClick={handleSaveClick}
      >
        <SaveIcon strokeWidth={1.5} size={18} />
      </ControlButton>
    </Tooltip>
  );
};

export function useSaveNotebook() {
  const { saveLayout } = useRequestClient();
  const saveDocument = useNotebookDocumentSave();
  const { openModal, closeModal, openAlert } = useImperativeModal();
  const updateFilename = useUpdateFilename();
  const store = useStore();

  // Save the notebook the host has a file for.
  const saveNotebook = useEvent((userInitiated: boolean) =>
    enqueueNotebookSave(async () => {
      const connection = store.get(connectionAtom);
      const autoSaveConfig = store.get(autoSaveConfigAtom);

      if (!store.get(canEditAtom)) {
        return;
      }

      // Don't save if we are not connected to a kernel
      if (connection.state !== ConnectionState.OPEN) {
        openAlert("Failed to save notebook: not connected to a kernel.");
        return;
      }

      if (userInitiated && autoSaveConfig.format_on_save) {
        Logger.log("formatting notebook (onSave)");
        await formatAll();
      }

      if (notebookCells(getNotebook()).length === 0) {
        return;
      }

      // The notebook is the host's document plus a layout the editor keeps
      // beside it. TODO: fold the layout into the host document.
      const layout = store.get(layoutStateAtom);
      try {
        await saveLayout({ layout: getSerializedLayout() });
        await saveDocument();
      } catch (error) {
        Logger.error("Failed to save notebook", error);
        toast({
          title: "Failed to save",
          description: error instanceof Error ? error.message : String(error),
          variant: "danger",
        });
        return;
      }
      store.set(savedLayoutAtom, layout);
    }),
  );

  // Save the notebook with the current filename, only if the filename exists
  const saveIfNotebookIsPersistent = useEvent((userInitiated = false) => {
    const filename = store.get(filenameAtom);
    const connection = store.get(connectionAtom);
    if (
      isNamedPersistentFile(filename) &&
      connection.state === ConnectionState.OPEN
    ) {
      saveNotebook(userInitiated);
    }
  });

  const handleSaveDialog = (pythonFilename: string) => {
    updateFilename(pythonFilename).then((name) => {
      if (name !== null) {
        saveNotebook(true);
      }
    });
  };

  // Save the notebook with the current filename, or prompt the user to name
  const saveOrNameNotebook = useEvent(() => {
    const filename = store.get(filenameAtom);
    const connection = store.get(connectionAtom);
    saveIfNotebookIsPersistent(true);

    // Filename does not exist and we are connected to a kernel
    if (
      !isNamedPersistentFile(filename) &&
      connection.state !== ConnectionState.CLOSED
    ) {
      openModal(<SaveDialog onClose={closeModal} onSave={handleSaveDialog} />);
    }
  });

  return {
    saveOrNameNotebook,
    saveIfNotebookIsPersistent,
    saveNotebook,
  };
}

export function isNamedPersistentFile(
  filename: string | null,
): filename is string {
  return (
    filename !== null &&
    // Linux
    !filename.startsWith("/tmp/") &&
    // macOS
    !filename.startsWith("/var/folders") &&
    // Windows
    !filename.includes("AppData\\Local\\Temp")
  );
}

export function useAutoSaveNotebook(opts: { onSave: () => void }) {
  const autoSaveConfig = useAtomValue(autoSaveConfigAtom);
  const canEdit = useAtomValue(canEditAtom);
  const [connection] = useAtom(connectionAtom);
  const needsSave = useAtomValue(needsSaveAtom);
  const version = useAtomValue(documentVersionAtom);

  useAutoSave({
    onSave: opts.onSave,
    needsSave: needsSave,
    version,
    connStatus: connection,
    config: autoSaveConfig,
    canEdit,
  });
}

const SaveDialog = (props: {
  onClose: () => void;
  onSave: (filename: string) => void;
}) => {
  const { onClose, onSave } = props;
  const cancelButtonLabel = "Cancel";
  const [filename, setFilename] = useState<string>();
  const handleFilenameChange = (name: string) => {
    setFilename(name);
    if (name.trim()) {
      onSave(name);
      onClose();
    }
  };

  return (
    <DialogContent>
      <DialogTitle>Save notebook</DialogTitle>
      <div className="flex flex-col">
        <Label className="text-md pt-6 px-1">Save as</Label>
        <FilenameInput
          onNameChange={handleFilenameChange}
          placeholderText="filename"
          className="missing-filename"
        />
      </div>
      <DialogFooter>
        <Button
          data-testid="cancel-save-dialog-button"
          aria-label={cancelButtonLabel}
          variant="secondary"
          onClick={onClose}
        >
          Cancel
        </Button>
        <Button
          data-testid="submit-save-dialog-button"
          aria-label="Save"
          variant="default"
          disabled={!filename}
          type="submit"
        >
          Save
        </Button>
      </DialogFooter>
    </DialogContent>
  );
};
