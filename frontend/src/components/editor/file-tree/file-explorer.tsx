/* Copyright 2024 Marimo. All rights reserved. */
import {
  type NodeApi,
  type NodeRendererProps,
  Tree,
  type TreeApi,
} from "react-arborist";

import React, { Suspense, use, useEffect, useRef, useState } from "react";
import {
  ArrowLeftIcon,
  BracesIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CopyIcon,
  CopyMinusIcon,
  Edit3Icon,
  ExternalLinkIcon,
  FilePlus2Icon,
  FolderPlusIcon,
  MoreVerticalIcon,
  PlaySquareIcon,
  RefreshCcwIcon,
  Trash2Icon,
  UploadIcon,
  ViewIcon,
  DownloadIcon,
} from "lucide-react";
import type { FileInfo } from "@/core/network/types";
import {
  FILE_TYPE_ICONS,
  type FileType,
  PYTHON_CODE_FOR_FILE_TYPE,
  guessFileType,
} from "./types";
import { toast } from "@/components/ui/use-toast";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
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
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { Spinner } from "@/components/icons/spinner";
import type { RequestingTree } from "./requesting-tree";
import type { FilePath } from "@/utils/paths";
import useEvent from "react-use-event-hook";
import { copyToClipboard } from "@/utils/copy";
import { openFile, sendFileDetails } from "@/core/network/requests";
import { downloadBlob } from "@/utils/download";

const RequestingTreeContext = React.createContext<RequestingTree | null>(null);

export const FileExplorer: React.FC<{
  height: number;
}> = ({ height }) => {
  const treeRef = useRef<TreeApi<FileInfo>>(null);
  const [tree] = useAtom(treeAtom);
  const [data, setData] = useState<FileInfo[]>([]);
  const [openFile, setOpenFile] = useState<FileInfo | null>(null);
  const { openPrompt } = useImperativeModal();
  // Keep external state to remember which folders are open
  // when this component is unmounted
  const [openState, setOpenState] = useAtom(openStateAtom);

  const { loading, error } = useAsyncData(() => tree.initialize(setData), []);

  const handleRefresh = useEvent(() => {
    tree.refreshAll(Object.keys(openState).filter((id) => openState[id]));
  });

  const handleCreateFolder = useEvent(async () => {
    openPrompt({
      title: "Folder name",
      onConfirm: async (name) => {
        tree.createFolder(name, null);
      },
    });
  });

  const handleCreateFile = useEvent(async () => {
    openPrompt({
      title: "File name",
      onConfirm: async (name) => {
        tree.createFile(name, null);
      },
    });
  });

  const handleCollapseAll = useEvent(() => {
    treeRef.current?.closeAll();
    setOpenState({});
  });

  if (loading) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (openFile) {
    return (
      <>
        <div className="flex items-center pl-1 pr-3 flex-shrink-0 border-b justify-between">
          <Button
            onClick={() => setOpenFile(null)}
            data-testid="file-explorer-back-button"
            variant="text"
            size="xs"
            className="mb-0"
          >
            <ArrowLeftIcon size={16} />
          </Button>
          <span className="font-bold">{openFile.name}</span>
        </div>
        <Suspense>
          <FileViewer
            onOpenNotebook={(evt) =>
              openMarimoNotebook(
                evt,
                tree.relativeFromRoot(openFile.path as FilePath),
              )
            }
            file={openFile}
          />
        </Suspense>
      </>
    );
  }

  return (
    <>
      <Toolbar
        onRefresh={handleRefresh}
        onCreateFile={handleCreateFile}
        onCreateFolder={handleCreateFolder}
        onCollapseAll={handleCollapseAll}
        tree={tree}
      />
      <RequestingTreeContext value={tree}>
        <Tree<FileInfo>
          width="100%"
          ref={treeRef}
          height={height - 33}
          className="h-full"
          data={data}
          initialOpenState={openState}
          openByDefault={false}
          // Hide the drop cursor
          renderCursor={() => null}
          // Disable dropping files into files
          disableDrop={({ parentNode }) => !parentNode.data.isDirectory}
          onDelete={async ({ ids }) => {
            for (const id of ids) {
              await tree.delete(id);
            }
          }}
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
      </RequestingTreeContext>
    </>
  );
};

const INDENT_STEP = 15;

interface ToolbarProps {
  onRefresh: () => void;
  onCreateFile: () => void;
  onCreateFolder: () => void;
  onCollapseAll: () => void;
  tree: RequestingTree;
}

const Toolbar = ({
  tree,
  onRefresh,
  onCreateFile,
  onCreateFolder,
  onCollapseAll,
}: ToolbarProps) => {
  const { getRootProps, getInputProps } = useFileExplorerUpload({
    noDrag: true,
    noDragEventsBubbling: true,
  });

  return (
    <div className="flex items-center justify-end px-2 flex-shrink-0 border-b">
      <Tooltip content="Add file">
        <Button
          data-testid="file-explorer-add-file-button"
          onClick={onCreateFile}
          variant="text"
          size="xs"
        >
          <FilePlus2Icon size={16} />
        </Button>
      </Tooltip>
      <Tooltip content="Add folder">
        <Button
          data-testid="file-explorer-add-folder-button"
          onClick={onCreateFolder}
          variant="text"
          size="xs"
        >
          <FolderPlusIcon size={16} />
        </Button>
      </Tooltip>
      <Tooltip content="Upload file">
        <button
          data-testid="file-explorer-upload-button"
          {...getRootProps({})}
          className={buttonVariants({
            variant: "text",
            size: "xs",
          })}
        >
          <UploadIcon size={16} />
        </button>
      </Tooltip>
      <input {...getInputProps({})} type="file" />
      <Tooltip content="Refresh">
        <Button
          data-testid="file-explorer-refresh-button"
          onClick={onRefresh}
          variant="text"
          size="xs"
        >
          <RefreshCcwIcon size={16} />
        </Button>
      </Tooltip>
      <Tooltip content="Collapse all folders">
        <Button
          data-testid="file-explorer-collapse-button"
          onClick={onCollapseAll}
          variant="text"
          size="xs"
        >
          <CopyMinusIcon size={16} />
        </Button>
      </Tooltip>
    </div>
  );
};

const Show = ({
  node,
  onOpenMarimoFile,
}: {
  node: NodeApi<FileInfo>;
  onOpenMarimoFile: (
    evt: Pick<Event, "stopPropagation" | "preventDefault">,
  ) => void;
}) => {
  return (
    <span
      className="flex-1 overflow-hidden text-ellipsis"
      onClick={(e) => {
        if (node.data.isDirectory) {
          return;
        }
        e.stopPropagation();
        node.select();
      }}
    >
      {node.data.name}
      {node.data.isMarimoFile && !isWasm() && (
        <span
          className="flex-shrink-0 ml-2 text-sm hidden group-hover:inline hover:underline"
          onClick={onOpenMarimoFile}
        >
          open <ExternalLinkIcon className="inline ml-1" size={12} />
        </span>
      )}
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
  const { openConfirm, openPrompt } = useImperativeModal();
  const tree = use(RequestingTreeContext);

  const handleOpenMarimoFile = async (
    evt: Pick<Event, "stopPropagation" | "preventDefault">,
  ) => {
    const path = tree
      ? tree.relativeFromRoot(node.data.path as FilePath)
      : node.data.path;
    openMarimoNotebook(evt, path);
  };

  const handleDeleteFile = async (evt: Event) => {
    evt.stopPropagation();
    evt.preventDefault();
    openConfirm({
      title: "Delete file",
      description: `Are you sure you want to delete ${node.data.name}?`,
      confirmAction: (
        <AlertDialogDestructiveAction
          onClick={async () => {
            await node.tree.delete(node.id);
          }}
          aria-label="Confirm"
        >
          Delete
        </AlertDialogDestructiveAction>
      ),
    });
  };

  const handleCreateFolder = useEvent(async () => {
    // If not expanded, then expand
    node.open();
    openPrompt({
      title: "Folder name",
      onConfirm: async (name) => {
        tree?.createFolder(name, node.id);
      },
    });
  });

  const handleCreateFile = useEvent(async () => {
    node.open();
    openPrompt({
      title: "File name",
      onConfirm: async (name) => {
        tree?.createFile(name, node.id);
      },
    });
  });

  const renderActions = () => {
    const iconProps = {
      size: 14,
      strokeWidth: 1.5,
      className: "mr-2",
    };
    return (
      <DropdownMenuContent
        align="end"
        className="no-print w-[220px]"
        onClick={(e) => e.stopPropagation()}
        onCloseAutoFocus={(e) => e.preventDefault()}
      >
        {!node.data.isDirectory && (
          <DropdownMenuItem onSelect={() => node.select()}>
            <ViewIcon {...iconProps} />
            Open file
          </DropdownMenuItem>
        )}
        {!node.data.isDirectory && !isWasm() && (
          <DropdownMenuItem
            onSelect={() => {
              openFile({ path: node.data.path });
            }}
          >
            <ExternalLinkIcon {...iconProps} />
            Open file in external editor
          </DropdownMenuItem>
        )}
        {node.data.isDirectory && (
          <>
            <DropdownMenuItem onSelect={() => handleCreateFile()}>
              <FilePlus2Icon {...iconProps} />
              Create file
            </DropdownMenuItem>
            <DropdownMenuItem onSelect={() => handleCreateFolder()}>
              <FolderPlusIcon {...iconProps} />
              Create folder
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onSelect={() => node.edit()}>
          <Edit3Icon {...iconProps} />
          Rename
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={async () => {
            await copyToClipboard(node.data.path);
            toast({ title: "Copied to clipboard" });
          }}
        >
          <CopyIcon {...iconProps} />
          Copy path
        </DropdownMenuItem>
        {tree && (
          <DropdownMenuItem
            onSelect={async () => {
              await copyToClipboard(
                tree.relativeFromRoot(node.data.path as FilePath),
              );
              toast({ title: "Copied to clipboard" });
            }}
          >
            <CopyIcon {...iconProps} />
            Copy relative path
          </DropdownMenuItem>
        )}
        <DropdownMenuItem
          onSelect={async () => {
            toast({
              title: "Copied to clipboard",
              description:
                "Code to open the file has been copied to your clipboard. You can also drag and drop this file into the editor",
            });
            const { path } = node.data;
            const pythonCode = PYTHON_CODE_FOR_FILE_TYPE[fileType](path);
            await copyToClipboard(pythonCode);
          }}
        >
          <BracesIcon {...iconProps} />
          Copy snippet for reading file
        </DropdownMenuItem>
        {/* Not shown in WASM */}
        {node.data.isMarimoFile && !isWasm() && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={handleOpenMarimoFile}>
              <PlaySquareIcon {...iconProps} />
              Open notebook
            </DropdownMenuItem>
          </>
        )}
        <DropdownMenuSeparator />
        {!node.data.isDirectory && (
          <>
            <DropdownMenuItem
              onSelect={async () => {
                const details = await sendFileDetails({ path: node.data.path });
                const contents = details.contents || "";
                downloadBlob(new Blob([contents]), node.data.name);
              }}
            >
              <DownloadIcon {...iconProps} />
              Download
            </DropdownMenuItem>
            <DropdownMenuSeparator />
          </>
        )}
        <DropdownMenuItem onSelect={handleDeleteFile} variant="danger">
          <Trash2Icon {...iconProps} />
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    );
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
          "flex items-center pl-1 py-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l flex-1 overflow-hidden group",
          node.willReceiveDrop &&
            node.data.isDirectory &&
            "bg-accent/80 hover:bg-accent/80 text-accent-foreground",
        )}
      >
        {node.data.isMarimoFile ? (
          <img
            src="./favicon.ico"
            className="w-5 h-5 flex-shrink-0 mr-2 filter grayscale"
            alt="Marimo"
          />
        ) : (
          <Icon className="w-5 h-5 flex-shrink-0 mr-2" strokeWidth={1.5} />
        )}
        {node.isEditing ? (
          <Edit node={node} />
        ) : (
          <Show node={node} onOpenMarimoFile={handleOpenMarimoFile} />
        )}
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger
            asChild={true}
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
          >
            <Button
              data-testid="file-explorer-more-button"
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
          {renderActions()}
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

function openMarimoNotebook(
  event: Pick<Event, "stopPropagation" | "preventDefault">,
  path: string,
) {
  event.stopPropagation();
  event.preventDefault();
  window.open(`/?file=${path}`, "_blank");
}
