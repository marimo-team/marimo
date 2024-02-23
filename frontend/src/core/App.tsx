/* Copyright 2024 Marimo. All rights reserved. */
import "../css/App.css";

import { HourglassIcon, UnlinkIcon } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import {
  sendInterrupt,
  sendRename,
  sendSave,
  sendShutdown,
} from "@/core/network/requests";

import { Controls } from "@/components/editor/controls/Controls";
import { DirCompletionInput } from "@/components/editor/DirCompletionInput";
import { FilenameForm } from "@/components/editor/FilenameForm";
import { WebSocketState } from "./websocket/types";
import { useMarimoWebSocket } from "./websocket/useMarimoWebSocket";
import {
  LastSavedNotebook,
  notebookCells,
  notebookIsRunning,
  notebookNeedsRun,
  notebookNeedsSave,
  useCellActions,
  useNotebook,
} from "./cells/cells";
import { Disconnected } from "../components/editor/Disconnected";
import { AppConfig, UserConfig } from "./config/config-schema";
import { toggleAppMode, viewStateAtom } from "./mode";
import { useHotkey } from "../hooks/useHotkey";
import { Tooltip } from "../components/ui/tooltip";
import { useImperativeModal } from "../components/modal/ImperativeModal";
import {
  DialogContent,
  DialogFooter,
  DialogTitle,
} from "../components/ui/dialog";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { useEvent } from "../hooks/useEvent";
import { Logger } from "../utils/Logger";
import { useAutoSave } from "./saving/useAutoSave";
import { useEventListener } from "../hooks/useEventListener";
import { toast } from "../components/ui/use-toast";
import { SortableCellsProvider } from "../components/sort/SortableCellsProvider";
import { CellId, HTMLCellId } from "./cells/ids";
import { CellArray } from "../components/editor/renderers/CellArray";
import { RuntimeState } from "./kernel/RuntimeState";
import { CellsRenderer } from "../components/editor/renderers/cells-renderer";
import { getSerializedLayout } from "./layout/layout";
import { useAtom } from "jotai";
import { useRunStaleCells } from "../components/editor/cell/useRunCells";
import { formatAll } from "./codemirror/format";
import { cn } from "@/utils/cn";
import { isStaticNotebook } from "./static/static-state";
import { useFilename } from "./saving/filename";
import { getSessionId } from "./kernel/session";

interface AppProps {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

export const App: React.FC<AppProps> = ({ userConfig, appConfig }) => {
  const notebook = useNotebook();
  const { setCells, updateCellCode } = useCellActions();
  const [viewState, setViewState] = useAtom(viewStateAtom);
  const [filename, setFilename] = useFilename();
  const [lastSavedNotebook, setLastSavedNotebook] =
    useState<LastSavedNotebook>();
  const { openModal, closeModal, openAlert } = useImperativeModal();

  const isEditing = viewState.mode === "edit";
  const isPresenting = viewState.mode === "present";
  const isReading = viewState.mode === "read";
  const isRunning = notebookIsRunning(notebook);

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
    autoInstantiate:
      userConfig.runtime.auto_instantiate || viewState.mode === "read",
    setCells: (cells) => {
      setCells(cells);
      const names = cells.map((cell) => cell.name);
      const codes = cells.map((cell) => cell.code);
      const configs = cells.map((cell) => cell.config);
      setLastSavedNotebook({ names, codes, configs });
    },
    sessionId: getSessionId(),
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
    },
  );

  const cells = notebookCells(notebook);
  const cellIds = cells.map((cell) => cell.id);
  const codes = cells.map((cell) => cell.code);
  const cellNames = cells.map((cell) => cell.name);
  const configs = cells.map((cell) => cell.config);
  const needsSave = notebookNeedsSave(notebook, lastSavedNotebook);

  // Save the notebook with the given filename
  const saveNotebook = useEvent((filename: string, userInitiated: boolean) => {
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
      cellIds: cellIds,
      codes,
      names: cellNames,
      filename,
      configs,
      layout: getSerializedLayout(),
    })
      .then(() => {
        if (userInitiated) {
          toast({ title: "Notebook saved" });
          if (userConfig.save.format_on_save) {
            formatAll(updateCellCode);
          }
        }
        setLastSavedNotebook({ names: cellNames, codes, configs });
      })
      .catch((error) => {
        openAlert(error.message);
      });
  });

  // Save the notebook with the current filename, only if the filename exists
  const saveIfNotebookIsNamed = useEvent((userInitiated = false) => {
    if (filename !== null && connStatus.state === WebSocketState.OPEN) {
      saveNotebook(filename, userInitiated);
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
        />,
      );
    }
  });

  useAutoSave({
    // Only run autosave if the file is named
    onSave: saveIfNotebookIsNamed,
    // Reset autosave when needsSave, or codes/configs have changed
    needsSave: needsSave,
    codes: codes,
    cellConfigs: configs,
    cellNames: cellNames,
    connStatus: connStatus,
    config: userConfig,
  });

  useEventListener(window, "beforeunload", (e: BeforeUnloadEvent) => {
    if (isStaticNotebook()) {
      return;
    }

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

  const runStaleCells = useRunStaleCells();

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
          (elem.parentNode as HTMLElement).id as HTMLCellId,
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
  useHotkey("global.runStale", () => {
    runStaleCells();
  });
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
        cells: cells.map((cell) => {
          return { name: cell.name, code: cell.code };
        }),
      },
      // no replacer
      null,
      // whitespace for indentation
      2,
    );
  });

  const editableCellsArray = (
    <CellArray
      notebook={notebook}
      connStatus={connStatus}
      mode={viewState.mode}
      userConfig={userConfig}
      appConfig={appConfig}
    />
  );

  const statusOverlay = (
    <>
      {connStatus.state === WebSocketState.OPEN && isRunning && <RunningIcon />}
      {connStatus.state === WebSocketState.CLOSED && <NoiseBackground />}
      {connStatus.state === WebSocketState.CLOSED && <DisconnectedIcon />}
    </>
  );

  return (
    <>
      {statusOverlay}
      <div
        id="App"
        className={cn(
          connStatus.state === WebSocketState.CLOSED && "disconnected",
          "bg-background w-full h-full text-textColor",
          "flex flex-col overflow-y-auto overflow-x-hidden",
          appConfig.width === "full" && "config-width-full",
        )}
      >
        <div
          className={cn(
            (isEditing || isPresenting) && "pt-4 sm:pt-12 pb-2 mb-4",
            isReading && "sm:pt-8",
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
        {cells.length > 0 && (
          <CellsRenderer appConfig={appConfig} mode={viewState.mode}>
            <SortableCellsProvider disabled={!isEditing}>
              {editableCellsArray}
            </SortableCellsProvider>
          </CellsRenderer>
        )}
      </div>

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
          needsRun={notebookNeedsRun(notebook)}
          undoAvailable={notebook.history.length > 0}
          appWidth={appConfig.width}
        />
      )}
    </>
  );
};

const topLeftStatus =
  "absolute top-3 left-4 m-0 flex items-center space-x-3 min-h-[28px] no-print pointer-events-auto z-30";
const DisconnectedIcon = () => (
  <Tooltip content="App disconnected">
    <div className={topLeftStatus}>
      <UnlinkIcon className="closed-app-icon" />
    </div>
  </Tooltip>
);

const RunningIcon = () => (
  <div
    className={topLeftStatus}
    data-testid="loading-indicator"
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
