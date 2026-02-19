/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import { FileIcon, HardDrive } from "lucide-react";
import React, { useCallback, useMemo } from "react";
import useResizeObserver from "use-resize-observer";
import { StorageInspector } from "@/components/storage/storage-inspector";
import { Accordion } from "@/components/ui/accordion";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { storageNamespacesAtom } from "@/core/storage/state";
import { cn } from "@/utils/cn";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import { TreeDndProvider } from "../../file-tree/dnd-wrapper";
import { FileExplorer } from "../../file-tree/file-explorer";
import { useFileExplorerUpload } from "../../file-tree/upload";
import {
  PanelAccordionContent,
  PanelAccordionItem,
  PanelAccordionTrigger,
  PanelBadge,
} from "./components";

type OpenSections = "files" | "remote-storage";

interface FileExplorerPanelState {
  openSections: OpenSections[];
  hasUserInteracted: boolean;
}

const fileExplorerPanelAtom = atomWithStorage<FileExplorerPanelState>(
  "marimo:file-explorer-panel:state",
  { openSections: ["files"], hasUserInteracted: false },
  jotaiJsonStorage,
);

const FileExplorerComponent: React.FC<{ height: number }> = ({ height }) => {
  const { getRootProps, getInputProps, isDragActive } = useFileExplorerUpload({
    noClick: true,
    noKeyboard: true,
  });

  return (
    <TreeDndProvider>
      <div
        {...getRootProps()}
        className={cn("flex flex-col overflow-hidden relative")}
        style={{ height }}
      >
        <input {...getInputProps()} />
        {isDragActive && (
          <div className="absolute inset-0 flex items-center uppercase justify-center text-xl font-bold text-primary/90 bg-accent/85 z-10 border-2 border-dashed border-primary/90 rounded-lg pointer-events-none">
            Drop files here
          </div>
        )}

        <FileExplorer height={height} />
      </div>
    </TreeDndProvider>
  );
};

// Height of each accordion trigger (px-3 py-2 text-xs = ~33px)
const TRIGGER_HEIGHT = 33;

const FileExplorerPanel: React.FC = () => {
  const { ref: panelRef, height: panelHeight = 500 } =
    useResizeObserver<HTMLDivElement>();
  const [state, setState] = useAtom(fileExplorerPanelAtom);

  const storageNamespaces = useAtomValue(storageNamespacesAtom);
  const remoteStorageConnections = storageNamespaces.length;

  const openSections = useMemo<OpenSections[]>(() => {
    if (!state.hasUserInteracted && remoteStorageConnections > 0) {
      if (state.openSections.includes("remote-storage")) {
        return state.openSections;
      }
      return [...state.openSections, "remote-storage"];
    }
    return state.openSections;
  }, [state.hasUserInteracted, state.openSections, remoteStorageConnections]);

  const handleValueChange = useCallback(
    (value: OpenSections[]) => {
      setState({
        openSections: value,
        hasUserInteracted: true,
      });
    },
    [setState],
  );

  const availableContent = panelHeight - TRIGGER_HEIGHT * 2;
  const storageIsOpen = openSections.includes("remote-storage");
  const bothOpen = storageIsOpen && openSections.includes("files");

  const storageMaxHeight = bothOpen
    ? Math.round(availableContent * 0.4)
    : availableContent;
  const fileTreeHeight = Math.max(
    200,
    bothOpen ? availableContent - storageMaxHeight : availableContent,
  );

  const storageInspectorEnabled = getFeatureFlag("storage_inspector");
  if (!storageInspectorEnabled) {
    return (
      <div ref={panelRef} className="h-full overflow-auto">
        <FileExplorerComponent height={panelHeight} />
      </div>
    );
  }

  return (
    <div ref={panelRef} className="h-full overflow-auto">
      <Accordion
        type="multiple"
        value={openSections}
        onValueChange={handleValueChange}
      >
        <PanelAccordionItem value="remote-storage">
          <PanelAccordionTrigger>
            <HardDrive className="w-4 h-4" /> Remote storage
            {remoteStorageConnections > 0 && (
              <PanelBadge>{remoteStorageConnections}</PanelBadge>
            )}
          </PanelAccordionTrigger>
          <PanelAccordionContent
            className="overflow-auto"
            style={{ maxHeight: storageMaxHeight }}
          >
            <StorageInspector />
          </PanelAccordionContent>
        </PanelAccordionItem>

        <PanelAccordionItem value="files">
          <PanelAccordionTrigger>
            <FileIcon className="w-4 h-4" />
            Files
          </PanelAccordionTrigger>
          <PanelAccordionContent>
            <FileExplorerComponent height={fileTreeHeight} />
          </PanelAccordionContent>
        </PanelAccordionItem>
      </Accordion>
    </div>
  );
};

export default FileExplorerPanel;
