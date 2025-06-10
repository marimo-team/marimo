/* Copyright 2024 Marimo. All rights reserved. */
import {
  LayoutTemplateIcon,
  EditIcon,
  PlayIcon,
  SquareIcon,
  Undo2Icon,
} from "lucide-react";

import { Button } from "@/components/editor/inputs/Inputs";
import { KeyboardShortcuts } from "@/components/editor/controls/keyboard-shortcuts";
import { ShutdownButton } from "@/components/editor/controls/shutdown-button";

import { Tooltip } from "../../ui/tooltip";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import {
  canUndoDeletesAtom,
  needsRunAtom,
  useCellActions,
} from "../../../core/cells/cells";
import { ConfigButton } from "../../app-config/app-config-button";
import { LayoutSelect } from "../renderers/layout-select";
import { NotebookMenuDropdown } from "@/components/editor/controls/notebook-menu-dropdown";
import { FindReplace } from "@/components/find-replace/find-replace";
import type { AppConfig } from "@/core/config/config-schema";
import { useShouldShowInterrupt } from "../cell/useShouldShowInterrupt";
import { CommandPaletteButton } from "./command-palette-button";
import { cn } from "@/utils/cn";
import { HideInKioskMode } from "../kiosk-mode";
import { Functions } from "@/utils/functions";
import { SaveComponent } from "@/core/saving/save-component";
import { useAtomValue } from "jotai";

import type { JSX } from "react";

interface ControlsProps {
  presenting: boolean;
  onTogglePresenting: () => void;
  onInterrupt: () => void;
  onRun: () => void;
  closed: boolean;
  running: boolean;
  appConfig: AppConfig;
}

export const Controls = ({
  presenting,
  onTogglePresenting,
  onInterrupt,
  onRun,
  closed,
  running,
  appConfig,
}: ControlsProps): JSX.Element => {
  const appWidth = appConfig.width;
  const undoAvailable = useAtomValue(canUndoDeletesAtom);
  const needsRun = useAtomValue(needsRunAtom);
  const { undoDeleteCell } = useCellActions();

  let undoControl: JSX.Element | null = null;
  if (!closed && undoAvailable) {
    undoControl = (
      <Tooltip content="Undo cell deletion">
        <Button
          data-testid="undo-delete-cell"
          size="medium"
          color="hint-green"
          shape="circle"
          onClick={undoDeleteCell}
        >
          <Undo2Icon size={16} strokeWidth={1.5} />
        </Button>
      </Tooltip>
    );
  }

  return (
    <>
      {!presenting && <FindReplace />}

      {!closed && (
        <div className={topRightControls}>
          {presenting && <LayoutSelect />}
          <NotebookMenuDropdown />
          <ConfigButton />
          <ShutdownButton description="This will terminate the Python kernel. You'll lose all data that's in memory." />
        </div>
      )}

      <div
        className={cn(
          bottomRightControls,
          appWidth === "compact" && "xl:flex-row items-end",
        )}
      >
        <HideInKioskMode>
          <SaveComponent kioskMode={false} />
        </HideInKioskMode>

        <Tooltip content={renderShortcut("global.hideCode")}>
          <Button
            data-testid="hide-code-button"
            id="preview-button"
            shape="rectangle"
            color="hint-green"
            onClick={onTogglePresenting}
          >
            {presenting ? (
              <EditIcon strokeWidth={1.5} size={18} />
            ) : (
              <LayoutTemplateIcon strokeWidth={1.5} size={18} />
            )}
          </Button>
        </Tooltip>

        <CommandPaletteButton />
        <KeyboardShortcuts />

        <div />

        <HideInKioskMode>
          <div className="flex flex-col gap-2 items-center">
            {undoControl}
            {!closed && (
              <StopControlButton running={running} onInterrupt={onInterrupt} />
            )}
            {!closed && <RunControlButton needsRun={needsRun} onRun={onRun} />}
          </div>
        </HideInKioskMode>
      </div>
    </>
  );
};

const RunControlButton = ({
  needsRun,
  onRun,
}: {
  needsRun: boolean;
  onRun: () => void;
}) => {
  if (needsRun) {
    return (
      <Tooltip content={renderShortcut("global.runStale")}>
        <Button
          data-testid="run-button"
          size="medium"
          color="yellow"
          shape="circle"
          onClick={onRun}
        >
          <PlayIcon strokeWidth={1.5} size={16} />
        </Button>
      </Tooltip>
    );
  }

  return (
    <Tooltip content="Nothing to run">
      <Button
        data-testid="run-button"
        className={"inactive-button"}
        color="disabled"
        size="medium"
        shape="circle"
      >
        <PlayIcon strokeWidth={1.5} size={16} />
      </Button>
    </Tooltip>
  );
};

const StopControlButton = ({
  running,
  onInterrupt,
}: {
  running: boolean;
  onInterrupt: () => void;
}) => {
  // Show the interrupt button after 200ms to avoid flickering.
  const showInterrupt = useShouldShowInterrupt(running);

  return (
    <Tooltip content={renderShortcut("global.interrupt")}>
      <Button
        className={cn(
          !showInterrupt && "inactive-button active:shadow-xsSolid",
        )}
        data-testid="interrupt-button"
        size="medium"
        color={showInterrupt ? "yellow" : "disabled"}
        shape="circle"
        onClick={showInterrupt ? onInterrupt : Functions.NOOP}
      >
        <SquareIcon strokeWidth={1.5} size={16} />
      </Button>
    </Tooltip>
  );
};

const topRightControls =
  "absolute top-3 right-5 m-0 flex items-center space-x-3 min-h-[28px] no-print pointer-events-auto z-30 print:hidden";

const bottomRightControls =
  "absolute bottom-5 right-5 flex flex-col gap-2 items-center no-print pointer-events-auto z-30 print:hidden";
