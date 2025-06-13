/* Copyright 2024 Marimo. All rights reserved. */

import { usePrevious } from "@dnd-kit/utilities";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { useAtomValue, useSetAtom } from "jotai";
import { useEffect } from "react";
import { Controls } from "@/components/editor/controls/Controls";
import { AppHeader } from "@/components/editor/header/app-header";
import { FilenameForm } from "@/components/editor/header/filename-form";
import { sendComponentValues, sendInterrupt } from "@/core/network/requests";
import { cn } from "@/utils/cn";
import { Paths } from "@/utils/paths";
import { AppContainer } from "../components/editor/app-container";
import {
  useRunAllCells,
  useRunStaleCells,
} from "../components/editor/cell/useRunCells";
import { CellArray } from "../components/editor/renderers/CellArray";
import { CellsRenderer } from "../components/editor/renderers/cells-renderer";
import { useHotkey } from "../hooks/useHotkey";
import {
  cellIdsAtom,
  hasCellsAtom,
  notebookIsRunningAtom,
  numColumnsAtom,
  useCellActions,
} from "./cells/cells";
import { CellEffects } from "./cells/effects";
import type { AppConfig, UserConfig } from "./config/config-schema";
import { RuntimeState } from "./kernel/RuntimeState";
import { getSessionId } from "./kernel/session";
import { useTogglePresenting } from "./layout/useTogglePresenting";
import { viewStateAtom } from "./mode";
import { useFilename } from "./saving/filename";
import { lastSavedNotebookAtom } from "./saving/state";
import { useJotaiEffect } from "./state/jotai";
import { WebSocketState } from "./websocket/types";
import { useMarimoWebSocket } from "./websocket/useMarimoWebSocket";

interface AppProps {
  /**
   * The user config.
   */
  userConfig: UserConfig;
  /**
   * The app config.
   */
  appConfig: AppConfig;
  /**
   * If true, the floating controls will be hidden.
   */
  hideControls?: boolean;
}

export const EditApp: React.FC<AppProps> = ({
  userConfig,
  appConfig,
  hideControls = false,
}) => {
  useJotaiEffect(cellIdsAtom, CellEffects.onCellIdsChange);

  const { setCells, mergeAllColumns, collapseAllCells, expandAllCells } =
    useCellActions();
  const viewState = useAtomValue(viewStateAtom);
  const numColumns = useAtomValue(numColumnsAtom);
  const hasCells = useAtomValue(hasCellsAtom);
  const filename = useFilename();
  const setLastSavedNotebook = useSetAtom(lastSavedNotebookAtom);

  const isEditing = viewState.mode === "edit";
  const isPresenting = viewState.mode === "present";
  const isRunning = useAtomValue(notebookIsRunningAtom);

  // Initialize RuntimeState event-listeners
  useEffect(() => {
    RuntimeState.INSTANCE.start(sendComponentValues);
    return () => {
      RuntimeState.INSTANCE.stop();
    };
  }, []);

  const { connection } = useMarimoWebSocket({
    autoInstantiate: userConfig.runtime.auto_instantiate,
    setCells: (cells, layout) => {
      setCells(cells);
      const names = cells.map((cell) => cell.name);
      const codes = cells.map((cell) => cell.code);
      const configs = cells.map((cell) => cell.config);
      setLastSavedNotebook({ names, codes, configs, layout });
    },
    sessionId: getSessionId(),
  });

  // Update document title whenever filename or app_title changes
  useEffect(() => {
    // Set document title: app_title takes precedence, then filename, then default
    document.title =
      appConfig.app_title ||
      Paths.basename(filename ?? "") ||
      "Untitled Notebook";
  }, [appConfig.app_title, filename]);

  // Delete column breakpoints if app width changes from "columns"
  const previousWidth = usePrevious(appConfig.width);
  useEffect(() => {
    if (previousWidth === "columns" && appConfig.width !== "columns") {
      mergeAllColumns();
    }
  }, [appConfig.width, previousWidth, mergeAllColumns, numColumns]);

  const runStaleCells = useRunStaleCells();
  const runAllCells = useRunAllCells();
  const togglePresenting = useTogglePresenting();

  // HOTKEYS
  useHotkey("global.runStale", () => {
    runStaleCells();
  });
  useHotkey("global.interrupt", () => {
    sendInterrupt();
  });
  useHotkey("global.hideCode", () => {
    togglePresenting();
  });
  useHotkey("global.runAll", () => {
    runAllCells();
  });
  useHotkey("global.collapseAllSections", () => {
    collapseAllCells();
  });
  useHotkey("global.expandAllSections", () => {
    expandAllCells();
  });

  const editableCellsArray = (
    <CellArray
      connStatus={connection}
      mode={viewState.mode}
      userConfig={userConfig}
      appConfig={appConfig}
    />
  );

  return (
    <>
      <AppContainer
        connection={connection}
        isRunning={isRunning}
        width={appConfig.width}
      >
        <AppHeader
          connection={connection}
          className={cn(
            "pt-4 sm:pt-12 pb-2 mb-4 print:hidden z-50",
            // Keep the header sticky when scrolling horizontally, for column mode
            "sticky left-0",
          )}
        >
          {isEditing && (
            <div className="flex items-center justify-center container">
              <FilenameForm filename={filename} />
            </div>
          )}
        </AppHeader>

        {/* Don't render until we have a single cell */}
        {hasCells && (
          <CellsRenderer appConfig={appConfig} mode={viewState.mode}>
            {editableCellsArray}
          </CellsRenderer>
        )}
      </AppContainer>
      {!hideControls && (
        <TooltipProvider>
          <Controls
            presenting={isPresenting}
            onTogglePresenting={togglePresenting}
            onInterrupt={sendInterrupt}
            onRun={runStaleCells}
            closed={connection.state === WebSocketState.CLOSED}
            running={isRunning}
            appConfig={appConfig}
          />
        </TooltipProvider>
      )}
    </>
  );
};
