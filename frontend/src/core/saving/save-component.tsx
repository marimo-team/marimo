/* Copyright 2024 Marimo. All rights reserved. */
import { useState } from "react";

import { sendSave } from "@/core/network/requests";

import { FilenameInput } from "@/components/editor/header/filename-input";
import { WebSocketState } from "../websocket/types";
import { useNotebook, getCellConfigs } from "../cells/cells";
import { notebookCells } from "../cells/utils";
import type { AppConfig } from "../config/config-schema";
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
import { getSerializedLayout, useLayoutState } from "../layout/layout";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { formatAll } from "../codemirror/format";
import { useFilename, useUpdateFilename } from "./filename";
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

interface SaveNotebookProps {
  kioskMode: boolean;
  appConfig: AppConfig;
}

export const SaveComponent = ({ kioskMode, appConfig }: SaveNotebookProps) => {
  const filename = useFilename();
  const { saveOrNameNotebook, needsSave, closed } = useSaveNotebook({
    appConfig,
    kioskMode,
  });

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

export function useSaveNotebook({ kioskMode }: SaveNotebookProps) {
  const autoSaveConfig = useAtomValue(autoSaveConfigAtom);
  const notebook = useNotebook();
  const [connection] = useAtom(connectionAtom);
  const filename = useFilename();
  const { openModal, closeModal, openAlert } = useImperativeModal();
  const setLastSavedNotebook = useSetAtom(lastSavedNotebookAtom);
  const updateFilename = useUpdateFilename();
  const needsSave = useAtomValue(needsSaveAtom);
  const layout = useLayoutState();

  // Save the notebook with the given filename
  const saveNotebook = useEvent((filename: string, userInitiated: boolean) => {
    const cells = notebookCells(notebook);
    const cellIds = cells.map((cell) => cell.id);
    const codes = cells.map((cell) => cell.code);
    const cellNames = cells.map((cell) => cell.name);
    const configs = getCellConfigs(notebook);

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
  const saveIfNotebookIsNamed = useEvent((userInitiated = false) => {
    if (filename !== null && connection.state === WebSocketState.OPEN) {
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
    saveIfNotebookIsNamed(true);

    // Filename does not exist and we are connected to a kernel
    if (filename === null && connection.state !== WebSocketState.CLOSED) {
      openModal(<SaveDialog onClose={closeModal} onSave={handleSaveDialog} />);
    }
  });

  const cells = notebookCells(notebook);
  const codes = cells.map((cell) => cell.code);
  const cellNames = cells.map((cell) => cell.name);
  const configs = getCellConfigs(notebook);

  useAutoSave({
    onSave: saveIfNotebookIsNamed,
    needsSave: needsSave,
    codes: codes,
    cellConfigs: configs,
    cellNames: cellNames,
    connStatus: connection,
    config: autoSaveConfig,
    kioskMode: kioskMode,
  });

  return {
    saveOrNameNotebook,
    needsSave,
    closed: connection.state === WebSocketState.CLOSED,
  };
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
