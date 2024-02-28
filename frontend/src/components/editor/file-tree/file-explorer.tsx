/* Copyright 2024 Marimo. All rights reserved. */
import { NodeApi, NodeRendererProps, Tree } from "react-arborist";

import React, { useEffect, useRef, useState } from "react";
import {
  ArrowLeftIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CopyIcon,
  Edit3Icon,
  MoreVerticalIcon,
  PlaySquareIcon,
  RefreshCcwIcon,
  UploadIcon,
  ViewIcon,
} from "lucide-react";
import { useOnMount } from "@/hooks/useLifecycle";
import { openFile } from "@/core/network/requests";
import { FileInfo } from "@/core/network/types";
import {
  FILE_TYPE_ICONS,
  FileType,
  PYTHON_CODE_FOR_FILE_TYPE,
  guessFileType,
} from "./types";
import { toast } from "@/components/ui/use-toast";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogAction } from "@/components/ui/alert-dialog";
import { useAtom } from "jotai";
import { Button, buttonVariants } from "@/components/ui/button";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { FileViewer } from "./file-viewer";
import { treeAtom, openStateAtom } from "./state";
import { useFileExplorerUpload } from "./upload";

export const FileExplorer: React.FC<{
  height: number;
}> = ({ height }) => {
  const [tree] = useAtom(treeAtom);
  const [data, setData] = useState<FileInfo[]>([]);
  const [openState, setOpenState] = useAtom(openStateAtom);
  const [openFile, setOpenFile] = useState<FileInfo | null>(null);

  useOnMount(() => {
    void tree.initialize(setData);
  });

  if (openFile) {
    return (
      <>
        <div className="flex items-center pl-1 pr-3 flex-shrink-0 border-b justify-between">
          <Button
            onClick={() => setOpenFile(null)}
            variant="text"
            size="xs"
            className="mb-0"
          >
            <ArrowLeftIcon size={16} />
          </Button>
          <span className="font-bold">{openFile.name}</span>
        </div>
        <FileViewer file={openFile} />
      </>
    );
  }

  return (
    <>
      <Toolbar
        onRefresh={() =>
          tree.refreshAll(Object.keys(openState).filter((id) => openState[id]))
        }
      />
      <Tree<FileInfo>
        width="100%"
        height={height - 26}
        className="h-full"
        data={data}
        initialOpenState={openState}
        openByDefault={false}
        // Hide the drop cursor
        renderCursor={() => null}
        // Disable dropping files into files
        disableDrop={({ parentNode }) => !parentNode.data.isDirectory}
        onRename={async ({ id, name }) => {
          await tree.rename(id, name);
        }}
        onMove={async ({ dragIds, parentId }) => {
          await tree.move(dragIds, parentId);
        }}
        onSelect={(nodes) => {
          const first = nodes[0];
          if (!first) {
            return;
          }
          if (!first.data.isDirectory) {
            setOpenFile(first.data);
          }
        }}
        onToggle={async (id) => {
          const result = await tree.expand(id);
          if (result) {
            const prevOpen = openState[id] ?? false;
            setOpenState({ ...openState, [id]: !prevOpen });
          }
        }}
        padding={15}
        rowHeight={30}
        indent={INDENT_STEP}
        overscanCount={1000}
        // Disable multi-selection
        disableMultiSelection={true}
      >
        {Node}
      </Tree>
    </>
  );
};

const INDENT_STEP = 15;

const Toolbar = ({ onRefresh }: { onRefresh: () => void }) => {
  const { getRootProps, getInputProps } = useFileExplorerUpload({
    noDrag: true,
    noDragEventsBubbling: true,
  });

  return (
    <div className="flex items-center justify-end px-2 flex-shrink-0 border-b">
      <Tooltip content="Upload file">
        <button
          {...getRootProps({})}
          className={buttonVariants({
            variant: "text",
            size: "xs",
            className: "mb-0",
          })}
        >
          <UploadIcon size={16} />
        </button>
      </Tooltip>
      <input {...getInputProps({})} type="file" />
      <Tooltip content="Refresh">
        <Button onClick={onRefresh} variant="text" size="xs" className="mb-0">
          <RefreshCcwIcon size={16} />
        </Button>
      </Tooltip>
    </div>
  );
};

const Show = ({ node }: { node: NodeApi<FileInfo> }) => {
  return (
    <span
      className="flex-1"
      onClick={(e) => {
        e.stopPropagation();
        if (node.data.isDirectory) {
          return;
        }
        node.select();
      }}
    >
      {node.data.name}
    </span>
  );
};

const Edit = ({ node }: { node: NodeApi<FileInfo> }) => {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
    // Select everything, but the extension
    ref.current?.setSelectionRange(0, node.data.name.lastIndexOf("."));
  }, [node.data.name]);

  return (
    <input
      ref={ref}
      className="flex-1 bg-transparent border border-border text-muted-foreground"
      defaultValue={node.data.name}
      onClick={(e) => e.stopPropagation()}
      onBlur={() => node.reset()}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          node.reset();
        }
        if (e.key === "Enter") {
          node.submit(e.currentTarget.value);
        }
      }}
    />
  );
};

const Node = ({ node, style, dragHandle }: NodeRendererProps<FileInfo>) => {
  const fileType: FileType = node.data.isDirectory
    ? "directory"
    : guessFileType(node.data.name);

  const Icon = FILE_TYPE_ICONS[fileType];
  const { openConfirm } = useImperativeModal();

  const handleOpenMarimoFile = async (evt: Event) => {
    evt.stopPropagation();
    evt.preventDefault();
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
  };

  return (
    <div
      style={style}
      ref={dragHandle}
      className={cn(
        "flex items-center cursor-pointer ml-1 text-muted-foreground whitespace-nowrap group",
      )}
      draggable={true}
      onClick={(evt) => {
        evt.stopPropagation();
        if (node.data.isDirectory) {
          node.toggle();
        }
      }}
    >
      <FolderArrow node={node} />
      <span
        className={cn(
          "flex items-center gap-2 px-1 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l flex-1",
          node.willReceiveDrop &&
            node.data.isDirectory &&
            "bg-accent/80 hover:bg-accent/80 text-accent-foreground",
        )}
      >
        <Icon className="w-5 h-5 flex-shrink-0" strokeWidth={1.5} />
        {node.isEditing ? <Edit node={node} /> : <Show node={node} />}
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger
            asChild={true}
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              variant="text"
              tabIndex={-1}
              size="xs"
              className="mb-0"
              aria-label="More options"
            >
              <MoreVerticalIcon
                strokeWidth={2}
                className="w-5 h-5 hidden group-hover:block"
              />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="no-print w-[220px]"
            onClick={(e) => e.stopPropagation()}
            onCloseAutoFocus={(e) => e.preventDefault()}
          >
            {!node.data.isDirectory && (
              <DropdownMenuItem onSelect={() => node.select()}>
                <ViewIcon className="mr-2" size={14} strokeWidth={1.5} />
                Open file
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={() => node.edit()}>
              <Edit3Icon className="mr-2" size={14} strokeWidth={1.5} />
              Rename
            </DropdownMenuItem>
            <DropdownMenuItem
              onSelect={() => {
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
              <CopyIcon className="mr-2" size={14} strokeWidth={1.5} />
              Copy snippet to clipboard
            </DropdownMenuItem>
            {node.data.isMarimoFile && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={handleOpenMarimoFile}>
                  <PlaySquareIcon
                    className="mr-2"
                    size={14}
                    strokeWidth={1.5}
                  />
                  Open notebook
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
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
