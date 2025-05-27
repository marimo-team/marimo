/* Copyright 2024 Marimo. All rights reserved. */

import { SlotNames } from "@/core/slots/slots";
import { Fill, Slot, useSlot } from "@marimo-team/react-slotz";
import { useAtom } from "jotai";
import type { PropsWithChildren } from "react";
import { PanelResizeHandle, Panel } from "react-resizable-panels";
import { handleDragging } from "../../wrapper/utils";
import { useResizeHandle } from "@/hooks/useResizeHandle";

import { PinIcon, PinOffIcon, XIcon, CrosshairIcon } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import { Toggle } from "@/components/ui/toggle";
import { ErrorBoundary } from "../../../boundary/ErrorBoundary";
import { cn } from "@/utils/cn";
import {
  contextAwarePanelOwner,
  isCellAwareAtom,
  isPinnedAtom,
  contextAwarePanelOpen,
} from "./atoms";

export const ContextAwarePanel: React.FC = () => {
  const [owner, setOwner] = useAtom(contextAwarePanelOwner);
  const [isPanelOpen, setIsPanelOpen] = useAtom(contextAwarePanelOpen);
  const [isPinned, setIsPinned] = useAtom(isPinnedAtom);
  const [isCellAware, setIsCellAware] = useAtom(isCellAwareAtom);

  const closePanel = () => {
    setOwner(null);
    setIsPanelOpen(false);
  };

  const slots = useSlot(SlotNames.CONTEXT_AWARE_PANEL);

  if (slots.length === 0 || !owner || !isPanelOpen) {
    return null;
  }

  const renderModeToggle = () => {
    return (
      <div className="flex flex-row items-center gap-3">
        <Tooltip content={isPinned ? "Unpin panel" : "Pin panel"}>
          <Toggle
            size="xs"
            onPressedChange={() => setIsPinned(!isPinned)}
            pressed={isPinned}
            aria-label={isPinned ? "Unpin panel" : "Pin panel"}
          >
            {isPinned ? (
              <PinIcon className="w-4 h-4" />
            ) : (
              <PinOffIcon className="w-4 h-4" />
            )}
          </Toggle>
        </Tooltip>
        <Tooltip
          content={
            isCellAware ? (
              <div className="flex flex-col gap-1">
                <span>Follow focused table</span>
                <span className="text-xs text-muted-foreground w-64">
                  The panel updates as cells that output tables are focused.
                  Click to fix to the current cell.
                </span>
              </div>
            ) : (
              <div className="flex flex-col gap-1">
                <span>Focus on current table</span>
                <span className="text-xs text-muted-foreground w-64">
                  The panel is focused on the current table. Click to update
                  based on which cell is focused.
                </span>
              </div>
            )
          }
        >
          <Toggle
            size="xs"
            onPressedChange={() => setIsCellAware(!isCellAware)}
            pressed={isCellAware}
            aria-label={isCellAware ? "Follow focused cell" : "Fixed"}
          >
            <CrosshairIcon
              className={cn("w-4 h-4", isCellAware && "text-primary")}
            />
          </Toggle>
        </Tooltip>
      </div>
    );
  };

  const renderBody = () => {
    return (
      <div className="mt-2 pb-7 mb-4 h-full overflow-auto">
        <div className="flex flex-row justify-between items-center mx-2">
          {renderModeToggle()}
          <Button
            variant="linkDestructive"
            size="icon"
            onClick={closePanel}
            aria-label="Close selection panel"
          >
            <XIcon className="w-4 h-4" />
          </Button>
        </div>

        {/* TODO: This usually doesn't trigger, and the whole panel closes */}
        <ErrorBoundary>
          <Slot name={SlotNames.CONTEXT_AWARE_PANEL} />
        </ErrorBoundary>
      </div>
    );
  };

  if (!isPinned) {
    return <ResizableComponent>{renderBody()}</ResizableComponent>;
  }

  return (
    <>
      <PanelResizeHandle
        onDragging={handleDragging}
        className="resize-handle border-border z-20 no-print border-l"
      />
      <Panel defaultSize={20} minSize={15} maxSize={80}>
        {renderBody()}
      </Panel>
    </>
  );
};

export const ContextAwarePanelItem: React.FC<PropsWithChildren> = ({
  children,
}) => {
  return (
    <ErrorBoundary>
      <Fill name={SlotNames.CONTEXT_AWARE_PANEL}>{children}</Fill>
    </ErrorBoundary>
  );
};

interface ResizableComponentProps {
  children: React.ReactNode;
}

const ResizableComponent = ({ children }: ResizableComponentProps) => {
  const { resizableDivRef, handleRefs, style } = useResizeHandle({
    startingWidth: 400,
    minWidth: 300,
    maxWidth: 1500,
  });

  return (
    <div className="absolute z-40 right-0 h-full bg-background flex flex-row">
      <div
        ref={handleRefs.left}
        className="w-1 h-full cursor-col-resize border-l"
      />
      <div ref={resizableDivRef} style={style}>
        {children}
      </div>
    </div>
  );
};
