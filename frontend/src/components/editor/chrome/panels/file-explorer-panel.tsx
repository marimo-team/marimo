/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { FileIcon, HardDrive } from "lucide-react";
import React, { useCallback, useMemo, useState } from "react";
import type { DropEvent } from "react-dropzone";
import useResizeObserver from "use-resize-observer";
import { StorageInspector } from "@/components/storage/storage-inspector";
import { Accordion } from "@/components/ui/accordion";
import { storageNamespacesAtom } from "@/core/storage/state";
import { useDetectedDataSources } from "@/hooks/useDataSourceDiscovery";
import { cn } from "@/utils/cn";
import type { FilePath } from "@/utils/paths";
import { TreeDndProvider } from "../../file-tree/dnd-wrapper";
import {
  FileExplorer,
  getUploadDestinationLabel,
} from "../../file-tree/file-explorer";
import { treeAtom } from "../../file-tree/state";
import {
  getUploadDestinationFromTarget,
  useFileExplorerUpload,
} from "../../file-tree/upload";
import {
  DiscoveredSourcesBadge,
  PanelAccordionContent,
  PanelAccordionItem,
  PanelAccordionTrigger,
  PanelBadge,
} from "./components";
import {
  fileExplorerPanelAtom,
  type FileExplorerPanelSection,
} from "./panel-accordion-state";

const FileExplorerComponent: React.FC<{ height: number }> = ({ height }) => {
  const tree = useAtomValue(treeAtom);
  const [dropDestinationPath, setDropDestinationPath] =
    useState<FilePath | null>(null);

  const getDropDestinationPath = useCallback(
    (event: DropEvent) =>
      getUploadDestinationForEvent(event, tree.getRootPath()),
    [tree],
  );
  const refreshUploadDestination = useCallback(
    (destinationPath: FilePath) => tree.refreshPath(destinationPath),
    [tree],
  );
  const { getRootProps, getInputProps, isDragActive } = useFileExplorerUpload({
    noClick: true,
    noKeyboard: true,
    destinationPath: getDropDestinationPath,
    getDestinationLabel: (path) => getUploadDestinationLabel(tree, path),
    refreshDestination: refreshUploadDestination,
    onDragEnter: (event) =>
      setDropDestinationPath(getDropDestinationPath(event)),
    onDragOver: (event) =>
      setDropDestinationPath(getDropDestinationPath(event)),
    onDragLeave: () => setDropDestinationPath(null),
    onUploadStart: () => setDropDestinationPath(null),
  });
  const displayedDestinationPath = dropDestinationPath ?? tree.getRootPath();
  const displayedDestinationLabel = getUploadDestinationLabel(
    tree,
    displayedDestinationPath,
  );

  return (
    <TreeDndProvider>
      <div
        {...getRootProps()}
        className={cn("flex flex-col overflow-hidden relative")}
        style={{ height }}
      >
        <input {...getInputProps()} />
        {isDragActive && (
          <div className="absolute inset-0 flex items-start justify-center pt-3 bg-accent/20 z-10 border-2 border-dashed border-primary/90 rounded-lg pointer-events-none">
            <span className="px-3 py-1.5 rounded-md bg-background/95 border shadow-sm text-sm font-semibold text-primary">
              Drop files into {displayedDestinationLabel}
            </span>
          </div>
        )}

        <FileExplorer
          height={height}
          externalDropDestinationPath={
            isDragActive ? displayedDestinationPath : null
          }
        />
      </div>
    </TreeDndProvider>
  );
};

export function getUploadDestinationForEvent(
  event: DropEvent,
  rootPath: FilePath,
): FilePath {
  if (Array.isArray(event)) {
    return rootPath;
  }
  return getUploadDestinationFromTarget(event.target, rootPath);
}

// Height of each accordion trigger (px-3 py-2 text-xs = ~33px)
const TRIGGER_HEIGHT = 33;

const FileExplorerPanel: React.FC = () => {
  const { ref: panelRef, height: panelHeight = 500 } =
    useResizeObserver<HTMLDivElement>();
  const [state, setState] = useAtom(fileExplorerPanelAtom);

  const storageNamespaces = useAtomValue(storageNamespacesAtom);
  const remoteStorageConnections = storageNamespaces.length;
  const pendingDataSources = useDetectedDataSources("storage");

  const openSections = useMemo<FileExplorerPanelSection[]>(() => {
    if (!state.hasUserInteracted && remoteStorageConnections > 0) {
      if (state.openSections.includes("remote-storage")) {
        return state.openSections;
      }
      return [...state.openSections, "remote-storage"];
    }
    return state.openSections;
  }, [state.hasUserInteracted, state.openSections, remoteStorageConnections]);

  const handleValueChange = useCallback(
    (value: FileExplorerPanelSection[]) => {
      setState({
        openSections: value,
        hasUserInteracted: true,
      });
    },
    [setState],
  );

  const availableContent = panelHeight - TRIGGER_HEIGHT * 2;
  const storageIsOpen = openSections.includes("remote-storage");
  const showDiscoveredStorageBadge = pendingDataSources.length > 0;
  const bothOpen = storageIsOpen && openSections.includes("files");

  const storageMaxHeight = bothOpen
    ? Math.round(availableContent * 0.4)
    : availableContent;
  const fileTreeHeight = Math.max(
    200,
    bothOpen ? availableContent - storageMaxHeight : availableContent,
  );

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
            {showDiscoveredStorageBadge && (
              <DiscoveredSourcesBadge
                count={pendingDataSources.length}
                type="storage"
              />
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
