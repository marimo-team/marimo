/* Copyright 2023 Marimo. All rights reserved. */
import "./css/App.css";

import { HourglassIcon, UnlinkIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  sendInterrupt,
  sendRename,
  sendRunMultiple,
  sendSave,
  sendShutdown,
} from "@/core/network/requests";

import { Controls } from "editor/Controls";
import { DirCompletionInput } from "editor/DirCompletionInput";
import { FilenameForm } from "editor/FilenameForm";
import { UUID } from "./utils/uuid";
import clsx from "clsx";
import { WebSocketState } from "./core/websocket/types";
import { useMarimoWebSocket } from "./core/websocket/useMarimoWebSocket";
import { useCellActions, useCells } from "./core/state/cells";
import { Disconnected } from "./editor/Disconnected";
import { derefNotNull } from "./utils/dereference";
import { AppConfig, UserConfig } from "./core/config/config";
import { toggleAppMode, viewStateAtom } from "./core/mode";
import { useHotkey } from "./hooks/useHotkey";
import { Tooltip } from "./components/ui/tooltip";
import { useImperativeModal } from "./components/modal/ImperativeModal";
import {
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "./components/ui/dialog";
import { Label } from "./components/ui/label";
import { Button } from "./components/ui/button";
import { useEvent } from "./hooks/useEvent";
import { Logger } from "./utils/Logger";
import { useAutoSave } from "./core/saving/useAutoSave";
import { useWindowEventListener } from "./hooks/useEventListener";
import { toast } from "./components/ui/use-toast";
import { SortableCellsProvider } from "./components/sort/SortableCellsProvider";
import { CellId, HTMLCellId } from "./core/model/ids";
import { getFilenameFromDOM } from "./core/dom/htmlUtils";
import { CellArray } from "./editor/renderers/CellArray";
import { RuntimeState } from "./core/RuntimeState";
import { CellsRenderer } from "./editor/renderers/cells-renderer";
import { getSerializedLayout } from "./core/state/layout";
import { useAtom } from "jotai";

interface AppProps {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

export const App: React.FC<AppProps> = ({ userConfig, appConfig }) => {
  const cells = useCells();
  const { setCells } = useCellActions();
  const [viewState, setViewState] = useAtom(viewStateAtom);
  const [filename, setFilename] = useState(getFilenameFromDOM());
  const [savedCodes, setSavedCodes] = useState<string[]>([""]);
  const { openModal, closeModal, openAlert } = useImperativeModal();

  const isEditing = viewState.mode === "edit";
  const isPresenting = viewState.mode === "present";
  const isReading = viewState.mode === "read";
  const isRunning = cells.present.some((cell) => cell.status === "running");

  function alertSaveFailed() {
    openAlert("Failed to save notebook: not connected to a kernel.");
  }

  // Initialize RuntimeState event-listeners
  useEffect(() => {
    RuntimeState.INSTANCE.start();
    return () => {
      RuntimeState.INSTANCE.stop();
    };
  }, []);

  const { connStatus } = useMarimoWebSocket({
    setCells,
    setInitialCodes: setSavedCodes,
    sessionId: UUID,
  });

  const handleFilenameChange = useEvent(
    (name: string | null): Promise<string | null> => {
      if (connStatus.state !== WebSocketState.OPEN) {
        alertSaveFailed();
        return Promise.resolve(null);
      }

      return sendRename(name)
        .then(() => {
          setFilename(name);
          return name;
        })
        .catch((error) => {
          openAlert(error.message);
          return null;
        });
    }
  );

  const codes = cells.present.map((cell) => cell.code);
  const cellNames = cells.present.map((cell) => cell.name);
  const needsSave =
    savedCodes.length !== codes.length ||
    savedCodes.some((code, index) => codes[index] !== code);

  // Save the notebook with the given filename
  const saveNotebook = useEvent((filename: string, showToast: boolean) => {
    // Don't save if there are no cells
    if (codes.length === 0) {
      return;
    }

    // Don't save if we are in read mode
    if (isReading) {
      return;
    }

    // Don't save if we are not connected to a kernel
    if (connStatus.state !== WebSocketState.OPEN) {
      alertSaveFailed();
      return;
    }

    Logger.log("saving to ", filename);
    sendSave({
      codes,
      names: cellNames,
      filename,
      layout: getSerializedLayout(),
    })
      .then(() => {
        if (showToast) {
          toast({ title: "Notebook saved" });
        }
        setSavedCodes(codes);
      })
      .catch((error) => {
        openAlert(error.message);
      });
  });

  // Save the notebook with the current filename, only if the filename exists
  const saveIfNotebookIsNamed = useEvent((showToast = false) => {
    if (filename !== null && connStatus.state === WebSocketState.OPEN) {
      saveNotebook(filename, showToast);
    }
  });

  // Save the notebook with the current filename, or prompt the user to name
  const saveOrNameNotebook = useEvent(() => {
    saveIfNotebookIsNamed(true);

    // Filename does not exist and we are connected to a kernel
    if (filename === null && connStatus.state !== WebSocketState.CLOSED) {
      openModal(
        <SaveDialog
          onClose={closeModal}
          onSubmitSaveDialog={onSubmitSaveDialog}
        />
      );
    }
  });

  useAutoSave({
    // Only run autosave if the file is named
    onSave: saveIfNotebookIsNamed,
    // Reset autosave when needsSave or codes have changed
    needsSave: needsSave,
    codes: codes,
    connStatus: connStatus,
    config: userConfig,
  });

  useWindowEventListener("beforeunload", (e: BeforeUnloadEvent) => {
    if (needsSave) {
      e.preventDefault();
      return (e.returnValue =
        "You have unsaved changes. Are you sure you want to quit?");
    }
  });

  const onSubmitSaveDialog = (e: React.FormEvent<HTMLFormElement>) => {
    const value = new FormData(e.currentTarget).get("SaveDialogInput");
    if (typeof value !== "string") {
      alert("Filename cannot be empty");
      return;
    }
    if (value.length === 0 || value === ".py") {
      alert("Filename cannot be empty");
      return;
    }

    const pythonFilename = value.endsWith(".py") ? value : `${value}.py`;
    handleFilenameChange(pythonFilename).then((name) => {
      if (name !== null) {
        saveNotebook(name, true);
      }
    });
  };

  const runStaleCells = useEvent(() => {
    const cellIds: CellId[] = [];
    const codes: string[] = [];
    for (const cell of cells.present) {
      if (cell.edited || cell.interrupted) {
        cellIds.push(cell.key);
        codes.push(derefNotNull(cell.ref).editorView.state.doc.toString());
        derefNotNull(cell.ref).registerRun();
      }
    }

    if (cellIds.length > 0) {
      RuntimeState.INSTANCE.registerRunStart();
      sendRunMultiple(cellIds, codes);
    }
  });

  // Toggle the array's presenting state, and sets a cell to anchor scrolling to
  const togglePresenting = useCallback(() => {
    const outputAreas = document.getElementsByClassName("output-area");
    const viewportEnd =
      window.innerHeight || document.documentElement.clientHeight;
    let cellAnchor: CellId | null = null;

    // Find the first output area that is visible
    // eslint-disable-next-line unicorn/prefer-spread
    for (const elem of Array.from(outputAreas)) {
      const rect = elem.getBoundingClientRect();
      if (
        (rect.top >= 0 && rect.top <= viewportEnd) ||
        (rect.bottom >= 0 && rect.bottom <= viewportEnd)
      ) {
        cellAnchor = HTMLCellId.parse(
          (elem.parentNode as HTMLElement).id as HTMLCellId
        );
        break;
      }
    }

    setViewState((prev) => ({
      mode: toggleAppMode(prev.mode),
      cellAnchor: cellAnchor,
    }));
    requestAnimationFrame(() => {
      if (cellAnchor === null) {
        return;
      }
      document.getElementById(HTMLCellId.create(cellAnchor))?.scrollIntoView();
    });
  }, [setViewState]);

  // HOTKEYS
  useHotkey("global.runStale", runStaleCells);
  useHotkey("global.save", saveOrNameNotebook);
  useHotkey("global.interrupt", () => {
    sendInterrupt();
  });
  useHotkey("global.hideCode", () => {
    if (isReading) {
      return;
    }
    togglePresenting();
  });

  const getCellsAsJSON = useEvent(() => {
    return JSON.stringify(
      {
        filename: filename,
        cells: cells.present.map((cell) => {
          return { name: cell.name, code: cell.code };
        }),
      },
      // no replacer
      null,
      // whitespace for indentation
      2
    );
  });

  const editableCellsArray = (
    <CellArray
      cells={cells}
      connStatus={connStatus}
      mode={viewState.mode}
      userConfig={userConfig}
      appConfig={appConfig}
    />
  );

  return (
    <div
      id="App"
      className={clsx(
        connStatus.state === WebSocketState.CLOSED && "disconnected",
        "bg-background w-full h-full text-textColor",
        "flex flex-col",
        appConfig.width === "full" && "config-width-full"
      )}
    >
      {connStatus.state === WebSocketState.OPEN && isRunning && <RunningIcon />}
      {connStatus.state === WebSocketState.CLOSED && <NoiseBackground />}
      {connStatus.state === WebSocketState.CLOSED && <DisconnectedIcon />}
      <div
        className={clsx(
          (isEditing || isPresenting) && "pt-4 sm:pt-12 pb-2 mb-4",
          (isPresenting || isReading) && "sm:pt-8"
        )}
      >
        {isEditing && (
          <div id="Welcome">
            <FilenameForm
              filename={filename}
              setFilename={handleFilenameChange}
            />
          </div>
        )}
        {connStatus.state === WebSocketState.CLOSED && (
          <Disconnected reason={connStatus.reason} />
        )}
      </div>

      {/* Don't render until we have a single cell */}
      {cells.present.length > 0 && isEditing && (
        <SortableCellsProvider disabled={!isEditing}>
          {editableCellsArray}
        </SortableCellsProvider>
      )}
      {cells.present.length > 0 && !isEditing && (
        <CellsRenderer appConfig={appConfig} mode={viewState.mode} />
      )}

      {(isEditing || isPresenting) && (
        <Controls
          filename={filename}
          needsSave={needsSave}
          onSaveNotebook={saveOrNameNotebook}
          getCellsAsJSON={getCellsAsJSON}
          presenting={isPresenting}
          onTogglePresenting={togglePresenting}
          onInterrupt={sendInterrupt}
          onShutdown={sendShutdown}
          onRun={runStaleCells}
          closed={connStatus.state === WebSocketState.CLOSED}
          running={isRunning}
          needsRun={cells.present.some(
            (cell) => cell.edited || cell.interrupted
          )}
          undoAvailable={cells.history.length > 0}
        />
      )}
    </div>
  );
};

const DisconnectedIcon = () => (
  <Tooltip content="App disconnected">
    <div className="app-status-indicator">
      <UnlinkIcon className="closed-app-icon" />
    </div>
  </Tooltip>
);

const RunningIcon = () => (
  <div
    className="app-status-indicator"
    title={"Marimo is busy computing. Hang tight!"}
  >
    <HourglassIcon className="running-app-icon" size={30} strokeWidth={1} />
  </div>
);

const NoiseBackground = () => (
  <>
    <div className="noise" />
    <div className="disconnected-gradient" />
  </>
);

const SaveDialog = (props: {
  onClose: () => void;
  onSubmitSaveDialog: (e: React.FormEvent<HTMLFormElement>) => void;
}) => {
  const { onClose, onSubmitSaveDialog } = props;
  const cancelButtonLabel = "Cancel";
  return (
    <DialogContent className="w-fit">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onSubmitSaveDialog(e);
          onClose();
        }}
        onKeyDown={(e) => {
          // We don't submit on Enter because the user may
          // have focused the cancel button ...
          if (e.key === "Escape") {
            onClose();
          } else if (
            e.key === "Enter" &&
            document.activeElement?.ariaLabel !== cancelButtonLabel
          ) {
            onSubmitSaveDialog(e);
            onClose();
          }
        }}
      >
        <DialogTitle className="text-accent mb-6">Save?</DialogTitle>
        <div className="flex items-center gap-5 mb-6 ml-4 mr-16">
          <Label className="text-md text-muted-foreground">Save as</Label>
          <DirCompletionInput
            name="SaveDialogInput"
            className="missing-filename"
          />
        </div>
        <DialogFooter>
          <Button
            aria-label={cancelButtonLabel}
            variant="secondary"
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button aria-label="Save" variant="default" type="submit">
            Save
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
};
