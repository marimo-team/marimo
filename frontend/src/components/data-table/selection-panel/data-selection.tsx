/* Copyright 2024 Marimo. All rights reserved. */

import { useResizeHandle } from "@/hooks/useResizeHandle";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandList,
} from "@/components/ui/command";
import { useAtom, useAtomValue } from "jotai";
import { XIcon, ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { PanelResizeHandle, Panel } from "react-resizable-panels";
import { selectionPanelOpenAtom, tableDataAtom } from "./panel-atoms";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

export const DataSelectionPanel: React.FC<{
  handleDragging: (isDragging: boolean) => void;
}> = ({ handleDragging }) => {
  // In overlay mode, the right panel overlaps the app body panel
  const [isOverlayMode, setIsOverlayMode] = useState(true);
  const [isOpen, setIsOpen] = useAtom(selectionPanelOpenAtom);
  const tableData = useAtomValue(tableDataAtom);

  if (!isOpen) {
    return null;
  }

  const renderModeToggle = () => {
    return (
      <div className="flex flex-row items-center gap-1">
        <Label>Overlay Mode</Label>
        <Switch
          checked={isOverlayMode}
          onCheckedChange={() => setIsOverlayMode(!isOverlayMode)}
          size="sm"
        />
      </div>
    );
  };

  const children = (
    <div className="mt-2">
      <div className="flex flex-row justify-between items-center my-1 mx-2">
        {renderModeToggle()}
        <Button
          variant="linkDestructive"
          size="icon"
          onClick={() => setIsOpen(false)}
          aria-label="Close selection panel"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>

      <h1 className="text-md font-bold tracking-wide text-center">
        Selection Panel
      </h1>

      <div className="flex flex-row gap-2 justify-end mr-2">
        <Button
          variant="outline"
          size="xs"
          className="px-1 h-5 w-5"
          // onClick={() => handleSelectRow(selectedRowIdx - 1)}
        >
          <ChevronLeft />
        </Button>
        <span className="text-sm">
          {/* {selectedRows.length > 0
              ? `${selectedRowIdx + 1} of ${selectedRows.length}`
              : "-"} */}
        </span>
        <Button
          variant="outline"
          size="xs"
          className="px-1 h-5 w-5"
          // onClick={() => handleSelectRow(selectedRowIdx + 1)}
        >
          <ChevronRight />
        </Button>
      </div>
      <Command>
        <CommandInput placeholder="Search columns..." />
        <CommandList className="max-h-full">
          <CommandEmpty>No columns found</CommandEmpty>
          {/* {items} */}
        </CommandList>
      </Command>
    </div>
  );

  if (isOverlayMode) {
    return <ResizableComponent>{children}</ResizableComponent>;
  }

  return (
    <>
      <PanelResizeHandle
        onDragging={handleDragging}
        className="resize-handle border-border z-20 no-print border-l"
      />
      <Panel>{children}</Panel>
    </>
  );
};

interface ResizableComponentProps {
  children: React.ReactNode;
}

const ResizableComponent = ({ children }: ResizableComponentProps) => {
  const { resizableDivRef, handleRef, style } = useResizeHandle({
    startingWidth: 400,
    direction: "left",
  });

  return (
    <div className="absolute z-40 right-0 h-full bg-background flex flex-row">
      <div ref={handleRef} className="w-1 h-full cursor-col-resize border-l" />
      <div ref={resizableDivRef} style={style}>
        {children}
      </div>
    </div>
  );
};
