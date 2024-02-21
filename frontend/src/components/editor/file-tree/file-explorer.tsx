/* Copyright 2024 Marimo. All rights reserved. */
import { NodeApi, NodeRendererProps, Tree, SimpleTree } from "react-arborist";

import React from "react";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  PlaySquareIcon,
} from "lucide-react";
import { useOnMount } from "@/hooks/useLifecycle";
import { openFile, sendListFiles } from "@/core/network/requests";
import { FileInfo } from "@/core/network/types";
import {
  FILE_TYPE_ICONS,
  FileType,
  PYTHON_CODE_FOR_FILE_TYPE,
  guessFileType,
} from "./types";
import { toast } from "@/components/ui/use-toast";
import { Tooltip } from "@/components/ui/tooltip";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogAction } from "@/components/ui/alert-dialog";
import { atom, useAtom } from "jotai";

// State lives outside of the component
// to preserve the state when the component is unmounted
const treeAtom = atom<SimpleTree<FileInfo>>(new SimpleTree<FileInfo>([]));
const openStateAtom = atom<Record<string, boolean>>({});

export const FileExplorer: React.FC<{
  height: number;
}> = ({ height }) => {
  const [tree, setTree] = useAtom(treeAtom);
  const [openState, setOpenState] = useAtom(openStateAtom);

  useOnMount(() => {
    if (tree.data.length > 0) {
      return;
    }
    // Fetch initial data on mount
    sendListFiles({ path: undefined }).then((data) => {
      setTree(new SimpleTree(data.files));
    });
  });

  // This is a HACK so that we don't opt into react-arborist's drag and drop
  // Their DnD implementation is removable and it causes issues with our
  // our own DnD
  const element = document.getElementById("noop-dnd-container");
  if (!element) {
    return null;
  }

  return (
    <>
      <Tree<FileInfo>
        width="100%"
        height={height}
        className="h-full"
        data={tree.data}
        dndRootElement={element}
        initialOpenState={openState}
        openByDefault={false}
        onToggle={(id) => {
          const node = tree.find(id);
          if (!node) {
            return;
          }
          if (!node.data.isDirectory) {
            return;
          }

          // We may attempt to load empty directories multiple times
          // but that is fine
          if (node.children && node.children.length > 0) {
            // Already loaded
            return;
          }

          sendListFiles({ path: id }).then((data) => {
            tree.update({ id, changes: { children: data.files } });
            setTree(new SimpleTree(tree.data));
            const prevOpen = openState[id] ?? false;
            setOpenState({ ...openState, [id]: !prevOpen });
          });
        }}
        padding={15}
        rowHeight={30}
        indent={INDENT_STEP}
        overscanCount={1000}
        // Disable all interactions
        disableMultiSelection={true}
        disableDrag={true}
        disableDrop={true}
        disableEdit={true}
      >
        {Node}
      </Tree>
      <div id="noop-dnd-container" />
    </>
  );
};

const INDENT_STEP = 15;

const Node = ({ node, style }: NodeRendererProps<FileInfo>) => {
  const fileType: FileType = node.data.isDirectory
    ? "directory"
    : guessFileType(node.data.name);

  const Icon = FILE_TYPE_ICONS[fileType];
  const { openConfirm } = useImperativeModal();

  return (
    <div
      style={style}
      className="flex items-center cursor-pointer ml-1 text-muted-foreground whitespace-nowrap"
      onClick={(evt) => {
        if (node.data.isDirectory) {
          node.toggle();
          evt.stopPropagation();
        }
      }}
    >
      <FolderArrow node={node} />
      <span
        className="flex items-center gap-2 px-1 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l flex-1"
        draggable={true}
        onDragStart={(e) => {
          const { path } = node.data;
          const pythonCode = PYTHON_CODE_FOR_FILE_TYPE[fileType](path);
          e.dataTransfer.setData("text/plain", pythonCode);
          e.stopPropagation();
        }}
        onClick={() => {
          if (node.data.isDirectory) {
            return;
          }

          toast({
            title: "Copied to clipboard",
            description:
              "Code to open the file has been copied to your clipboard. You can also drag and drop this file into the editor",
          });
          const { path } = node.data;
          const pythonCode = PYTHON_CODE_FOR_FILE_TYPE[fileType](path);
          navigator.clipboard.writeText(pythonCode);
        }}
      >
        <Icon className="w-5 h-5 flex-shrink-0" strokeWidth={1.5} />
        <span className="flex-1">{node.data.name}</span>
        {node.data.isMarimoFile ? (
          <Tooltip content="Open file">
            <PlaySquareIcon
              strokeWidth={1.5}
              onClick={async (e) => {
                e.stopPropagation();
                openConfirm({
                  title: "Open notebook",
                  description:
                    "This will close the current notebook and open the selected notebook. You'll lose all data that's in memory.",
                  confirmAction: (
                    <AlertDialogAction
                      onClick={async () => {
                        await openFile({ path: node.data.path });
                      }}
                      aria-label="Confirm"
                    >
                      Open
                    </AlertDialogAction>
                  ),
                });
              }}
            />
          </Tooltip>
        ) : null}
      </span>
    </div>
  );
};

const FolderArrow = ({ node }: { node: NodeApi<FileInfo> }) => {
  if (!node.data.isDirectory) {
    return <span className="w-5 h-5 flex-shrink-0" />;
  }

  return node.isOpen ? (
    <ChevronDownIcon className="w-5 h-5 flex-shrink-0" />
  ) : (
    <ChevronRightIcon className="w-5 h-5 flex-shrink-0" />
  );
};
