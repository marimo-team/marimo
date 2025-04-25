/* Copyright 2024 Marimo. All rights reserved. */
import { useState } from "react";

import { sendSave } from "@/core/network/requests";

import { FilenameInput } from "@/components/editor/header/filename-input";
import { WebSocketState } from "../websocket/types";
import { useNotebook, getCellConfigs, getNotebook } from "../cells/cells";
import { notebookCells } from "../cells/utils";
import { useImperativeModal } from "../../components/modal/ImperativeModal";
import {
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "../../components/ui/dialog";
import { Label } from "../../components/ui/label";
import { Button } from "../../components/ui/button";
import { useEvent } from "../../hooks/useEvent";
import { Logger } from "../../utils/Logger";
import { useAutoSave } from "./useAutoSave";
import { getSerializedLayout, layoutStateAtom } from "../layout/layout";
import { useAtom, useAtomValue, useSetAtom, useStore } from "jotai";
import { formatAll } from "../codemirror/format";
import { filenameAtom, useFilename, useUpdateFilename } from "./filename";
import { connectionAtom } from "../network/connection";
import { autoSaveConfigAtom } from "../config/config";
import { lastSavedNotebookAtom, needsSaveAtom } from "./state";
import { Tooltip } from "@/components/ui/tooltip";
import { RecoveryButton } from "@/components/editor/RecoveryButton";
import { renderShortcut } from "@/components/shortcuts/renderShortcut";
import { SaveIcon } from "lucide-react";
import { useHotkey } from "@/hooks/useHotkey";
import { Button as ControlButton } from "@/components/editor/inputs/Inputs";
import { useAutoExport } from "../export/hooks";
import { useEventListener } from "@/hooks/useEventListener";
import { kioskModeAtom } from "../mode";

interface SaveNotebookProps {
  kioskMode: boolean;
}

export const SaveComponent = ({ kioskMode }: SaveNotebookProps) => {
  const filename = useFilename();
  const needsSave = useAtomValue(needsSaveAtom);
  const closed = useAtomValue(connectionAtom).state === WebSocketState.CLOSED;
  const { saveOrNameNotebook, saveIfNotebookIsPersistent } = useSaveNotebook();
  useAutoSaveNotebook({ onSave: saveIfNotebookIsPersistent, kioskMode });

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
  const { openModal, closeModal, openAlert } = useImperativeModal();
  const setLastSavedNotebook = useSetAtom(lastSavedNotebookAtom);
  const updateFilename = useUpdateFilename();
  const store = useStore();

  // Save the notebook with the given filename
  const saveNotebook = useEvent((filename: string, userInitiated: boolean) => {
    const notebook = getNotebook();
    const cells = notebookCells(notebook);
    const cellIds = cells.map((cell) => cell.id);
    const codes = cells.map((cell) => cell.code);
    const cellNames = cells.map((cell) => cell.name);
    const configs = getCellConfigs(notebook);
    const connection = store.get(connectionAtom);
    const autoSaveConfig = store.get(autoSaveConfigAtom);
    const layout = store.get(layoutStateAtom);
    const kioskMode = store.get(kioskModeAtom);

    if (kioskMode) {
      return;
    }

    // Don't save if there are no cells
    if (codes.length === 0) {
      return;
    }

    // Don't save if we are not connected to a kernel
    if (connection.state !== WebSocketState.OPEN) {
      openAlert("Failed to save notebook: not connected to a kernel.");
      return;
    }

    Logger.log("saving to ", filename);
    sendSave({
      cellIds: cellIds,
      codes,
      names: cellNames,
      filename,
      configs,
      layout: getSerializedLayout(),
      persist: true,
    }).then(() => {
      if (userInitiated && autoSaveConfig.format_on_save) {
        formatAll();
      }
      setLastSavedNotebook({
        names: cellNames,
        codes,
        configs,
        layout,
      });
    });
  });

  // Save the notebook with the current filename, only if the filename exists
  const saveIfNotebookIsPersistent = useEvent((userInitiated = false) => {
    const filename = store.get(filenameAtom);
    const connection = store.get(connectionAtom);
    if (
      isNamedPersistentFile(filename) &&
      connection.state === WebSocketState.OPEN
    ) {
      saveNotebook(filename, userInitiated);
    }
  });

  const handleSaveDialog = (pythonFilename: string) => {
    updateFilename(pythonFilename).then((name) => {
      if (name !== null) {
        saveNotebook(name, true);
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
      connection.state !== WebSocketState.CLOSED
    ) {
      openModal(<SaveDialog onClose={closeModal} onSave={handleSaveDialog} />);
    }
  });

  return {
    saveOrNameNotebook,
    saveIfNotebookIsPersistent,
  };
}

function isNamedPersistentFile(filename: string | null): filename is string {
  return (
    filename !== null &&
    // Linux
    !filename.startsWith("/tmp") &&
    // macOS
    !filename.startsWith("/var/folders") &&
    // Windows
    !filename.includes("AppData\\Local\\Temp")
  );
}

export function useAutoSaveNotebook(opts: {
  onSave: () => void;
  kioskMode: boolean;
}) {
  const autoSaveConfig = useAtomValue(autoSaveConfigAtom);
  const notebook = useNotebook();
  const [connection] = useAtom(connectionAtom);
  const needsSave = useAtomValue(needsSaveAtom);

  const cells = notebookCells(notebook);
  const codes = cells.map((cell) => cell.code);
  const cellNames = cells.map((cell) => cell.name);
  const configs = getCellConfigs(notebook);

  useAutoSave({
    onSave: opts.onSave,
    needsSave: needsSave,
    codes: codes,
    cellConfigs: configs,
    cellNames: cellNames,
    connStatus: connection,
    config: autoSaveConfig,
    kioskMode: opts.kioskMode,
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
