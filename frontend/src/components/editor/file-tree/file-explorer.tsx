/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { atomWithStorage } from "jotai/utils";
import {
  ArrowLeftIcon,
  BetweenHorizontalStartIcon,
  BracesIcon,
  CopyMinusIcon,
  DownloadIcon,
  ExternalLinkIcon,
  EyeOffIcon,
  FilePlus2Icon,
  FolderPlusIcon,
  ListTreeIcon,
  PlaySquareIcon,
  UploadIcon,
  ViewIcon,
} from "lucide-react";
import React, { Suspense, use, useRef, useState } from "react";
import {
  type NodeApi,
  type NodeRendererProps,
  Tree,
  type TreeApi,
} from "react-arborist";
import useEvent from "react-use-event-hook";
import {
  FILE_ICON,
  FILE_ICON_COLOR,
  type FileIconType,
  guessFileIconType,
} from "@/components/editor/file-tree/file-icons";
import {
  DeleteMenuItem,
  DuplicateMenuItem,
  FileActionsDropdown,
  RenameMenuItem,
} from "@/components/editor/file-tree/file-operations";
import { FileNameInput } from "@/components/editor/file-tree/file-name-input";
import {
  MENU_ITEM_ICON_CLASS,
  RefreshIconButton,
  TreeChevron,
} from "@/components/editor/file-tree/tree-actions";
import { MarimoIcon, MarimoPlusIcon } from "@/components/icons/marimo-icons";
import { Spinner } from "@/components/icons/spinner";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { disableFileDownloadsAtom } from "@/core/config/config";
import { useRequestClient } from "@/core/network/requests";
import type { FileInfo } from "@/core/network/types";
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { deserializeBlob } from "@/utils/blob";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { downloadBlob } from "@/utils/download";
import { type Base64String, base64ToDataURL } from "@/utils/json/base64";
import { openNotebook } from "@/utils/links";
import type { FilePath } from "@/utils/paths";
import { makeDuplicateName } from "@/utils/pathUtils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import { useTreeDndManager } from "./dnd-wrapper";
import { FileViewer } from "./file-viewer";
import type { RequestingTree } from "./requesting-tree";
import { openStateAtom, treeAtom } from "./state";
import { PYTHON_CODE_FOR_FILE_TYPE } from "./types";
import { useFileExplorerUpload } from "./upload";

const hiddenFilesState = atomWithStorage(
  "marimo:showHiddenFiles",
  true,
  jotaiJsonStorage,
  {
    getOnInit: true,
  },
);

const RequestingTreeContext = React.createContext<RequestingTree | null>(null);

export const FileExplorer: React.FC<{
  height: number;
}> = ({ height }) => {
  const treeRef = useRef<TreeApi<FileInfo>>(null);
  const dndManager = useTreeDndManager();
  const [tree] = useAtom(treeAtom);
  const [data, setData] = useState<FileInfo[]>([]);
  const [openFile, setOpenFile] = useState<FileInfo | null>(null);
  const [showHiddenFiles, setShowHiddenFiles] =
    useAtom<boolean>(hiddenFilesState);

  const { openPrompt } = useImperativeModal();
  // Keep external state to remember which folders are open
  // when this component is unmounted
  const [openState, setOpenState] = useAtom(openStateAtom);
  const { isPending, error } = useAsyncData(() => tree.initialize(setData), []);

  const handleRefresh = useEvent(() => {
    // Return the promise so callers can await refresh completion
    return tree.refreshAll(
      Object.keys(openState).filter((id) => openState[id]),
    );
  });

  const handleHiddenFilesToggle = useEvent(() => {
    const newValue = !showHiddenFiles;
    setShowHiddenFiles(newValue);
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
        tree.createFile({ name, parentId: null });
      },
    });
  });

  const handleCreateNotebook = useEvent(async () => {
    openPrompt({
      title: "Notebook name",
      onConfirm: async (name) => {
        tree.createFile({ name, parentId: null, type: "notebook" });
      },
    });
  });

  const handleCollapseAll = useEvent(() => {
    treeRef.current?.closeAll();
    setOpenState({});
  });

  const visibleData = React.useMemo(
    () => filterHiddenTree(data, showHiddenFiles),
    [data, showHiddenFiles],
  );

  if (isPending) {
    return <Spinner size="medium" centered={true} />;
  }

  if (error) {
    return <ErrorBanner error={error} />;
  }

  if (openFile) {
    return (
      <>
        <div className="flex items-center pl-1 pr-3 shrink-0 border-b justify-between">
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
        onHidden={handleHiddenFilesToggle}
        onCreateFile={handleCreateFile}
        onCreateNotebook={handleCreateNotebook}
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
          data={visibleData}
          initialOpenState={openState}
          openByDefault={false}
          // Use shared DnD manager to prevent "Cannot have two HTML5 backends" error
          dndManager={dndManager}
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
  onHidden: () => void;
  onCreateFile: () => void;
  onCreateNotebook: () => void;
  onCreateFolder: () => void;
  onCollapseAll: () => void;
  tree: RequestingTree;
}

const Toolbar = ({
  onRefresh,
  onHidden,
  onCreateFile,
  onCreateNotebook,
  onCreateFolder,
  onCollapseAll,
}: ToolbarProps) => {
  const { getRootProps, getInputProps } = useFileExplorerUpload({
    noDrag: true,
    noDragEventsBubbling: true,
  });

  return (
    <div className="flex items-center justify-end px-2 shrink-0 border-b">
      <Tooltip content="Add notebook">
        <Button
          data-testid="file-explorer-add-notebook-button"
          onClick={onCreateNotebook}
          variant="text"
          size="xs"
        >
          <MarimoPlusIcon size={16} />
        </Button>
      </Tooltip>
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
      <RefreshIconButton
        data-testid="file-explorer-refresh-button"
        onClick={onRefresh}
      />
      <Tooltip content="Toggle hidden files">
        <Button
          data-testid="file-explorer-hidden-files-button"
          onClick={onHidden}
          variant="text"
          size="xs"
        >
          <EyeOffIcon size={16} />
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
          data-testid="file-explorer-open-marimo-button"
          className="shrink-0 ml-2 text-sm hidden group-hover:inline hover:underline"
          onClick={onOpenMarimoFile}
        >
          open <ExternalLinkIcon className="inline ml-1" size={12} />
        </span>
      )}
    </span>
  );
};

const Node = ({ node, style, dragHandle }: NodeRendererProps<FileInfo>) => {
  const { openFile, sendFileDetails } = useRequestClient();
  const disableFileDownloads = useAtomValue(disableFileDownloadsAtom);

  const fileType: FileIconType = node.data.isDirectory
    ? "directory"
    : guessFileIconType(node.data.name);

  const Icon = FILE_ICON[fileType];
  const { openConfirm, openPrompt } = useImperativeModal();
  const { createNewCell } = useCellActions();
  const lastFocusedCellId = useLastFocusedCellId();

  const handleInsertCode = (code: string) => {
    createNewCell({
      code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

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
        tree?.createFile({ name, parentId: node.id });
      },
    });
  });

  const handleCreateNotebook = useEvent(async () => {
    node.open();
    openPrompt({
      title: "Notebook name",
      onConfirm: async (name) => {
        tree?.createFile({ name, parentId: node.id, type: "notebook" });
      },
    });
  });

  const handleDuplicate = useEvent(async () => {
    if (!tree) {
      return;
    }
    await tree.copy(node.id, makeDuplicateName(node.data.name));
  });

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
          <MarimoIcon className="w-5 h-5 shrink-0 mr-2" strokeWidth={1.5} />
        ) : (
          <Icon
            className={cn("w-5 h-5 shrink-0 mr-2", FILE_ICON_COLOR[fileType])}
            strokeWidth={1.5}
          />
        )}
        {node.isEditing ? (
          <FileNameInput node={node} />
        ) : (
          <Show node={node} onOpenMarimoFile={handleOpenMarimoFile} />
        )}
        <FileActionsDropdown
          testId="file-explorer-more-button"
          iconClassName="w-5 h-5"
        >
          {!node.data.isDirectory && (
            <DropdownMenuItem onSelect={() => node.select()}>
              <ViewIcon className={MENU_ITEM_ICON_CLASS} />
              Open file
            </DropdownMenuItem>
          )}
          {!node.data.isDirectory && !isWasm() && (
            <DropdownMenuItem
              onSelect={() => {
                openFile({ path: node.data.path });
              }}
            >
              <ExternalLinkIcon className={MENU_ITEM_ICON_CLASS} />
              Open file in external editor
            </DropdownMenuItem>
          )}
          {node.data.isDirectory && (
            <>
              <DropdownMenuItem onSelect={() => handleCreateNotebook()}>
                <MarimoPlusIcon className={MENU_ITEM_ICON_CLASS} />
                Create notebook
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleCreateFile()}>
                <FilePlus2Icon className={MENU_ITEM_ICON_CLASS} />
                Create file
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleCreateFolder()}>
                <FolderPlusIcon className={MENU_ITEM_ICON_CLASS} />
                Create folder
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          <RenameMenuItem onSelect={() => node.edit()} />
          <DuplicateMenuItem onSelect={handleDuplicate} />
          <DropdownMenuItem
            onSelect={async () => {
              await copyToClipboard(node.data.path);
              toast({ title: "Copied to clipboard" });
            }}
          >
            <ListTreeIcon className={MENU_ITEM_ICON_CLASS} />
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
              <ListTreeIcon className={MENU_ITEM_ICON_CLASS} />
              Copy relative path
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            onSelect={() => {
              const { path } = node.data;
              const pythonCode = PYTHON_CODE_FOR_FILE_TYPE[fileType](path);
              handleInsertCode(pythonCode);
            }}
          >
            <BetweenHorizontalStartIcon className={MENU_ITEM_ICON_CLASS} />
            Insert snippet for reading file
          </DropdownMenuItem>
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
            <BracesIcon className={MENU_ITEM_ICON_CLASS} />
            Copy snippet for reading file
          </DropdownMenuItem>
          {node.data.isMarimoFile && !isWasm() && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={handleOpenMarimoFile}>
                <PlaySquareIcon className={MENU_ITEM_ICON_CLASS} />
                Open notebook
              </DropdownMenuItem>
            </>
          )}
          <DropdownMenuSeparator />
          {!node.data.isDirectory && !disableFileDownloads && (
            <>
              <DropdownMenuItem
                onSelect={async () => {
                  const details = await sendFileDetails({
                    path: node.data.path,
                  });
                  if (details.isBase64 && details.contents) {
                    const blob = deserializeBlob(
                      base64ToDataURL(
                        details.contents as Base64String,
                        details.mimeType || "application/octet-stream",
                      ),
                    );
                    downloadBlob(blob, node.data.name);
                  } else {
                    downloadBlob(
                      new Blob([details.contents || ""]),
                      node.data.name,
                    );
                  }
                }}
              >
                <DownloadIcon className={MENU_ITEM_ICON_CLASS} />
                Download
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          <DeleteMenuItem onSelect={handleDeleteFile} />
        </FileActionsDropdown>
      </span>
    </div>
  );
};

const FolderArrow = ({ node }: { node: NodeApi<FileInfo> }) => {
  if (!node.data.isDirectory) {
    return <span className="w-4 h-4 shrink-0" />;
  }

  return <TreeChevron isExpanded={node.isOpen} className="w-4 h-4" />;
};

function openMarimoNotebook(
  event: Pick<Event, "stopPropagation" | "preventDefault">,
  path: string,
) {
  event.stopPropagation();
  event.preventDefault();
  openNotebook(path);
}

export function filterHiddenTree(
  list: FileInfo[],
  showHidden: boolean,
): FileInfo[] {
  if (showHidden) {
    return list;
  }

  const out: FileInfo[] = [];
  for (const item of list) {
    if (isDirectoryOrFileHidden(item.name)) {
      continue;
    }
    let next = item;
    if (item.children) {
      const kids = filterHiddenTree(item.children, showHidden);
      if (kids !== item.children) {
        next = { ...item, children: kids };
      }
    }
    out.push(next);
  }
  return out;
}

export function isDirectoryOrFileHidden(filename: string): boolean {
  if (filename.startsWith(".")) {
    return true;
  }
  return false;
}
