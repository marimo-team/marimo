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
  FilePlus2Icon,
  FolderPlusIcon,
  FolderRootIcon,
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
  VisibilityToggleButton,
} from "@/components/editor/file-tree/tree-actions";
import { MarimoIcon, MarimoPlusIcon } from "@/components/icons/marimo-icons";
import { Spinner } from "@/components/icons/spinner";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
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
import { isWasm } from "@/core/wasm/utils";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { openNotebook } from "@/utils/links";
import type { FilePath } from "@/utils/paths";
import { makeDuplicateName } from "@/utils/pathUtils";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import { useTreeDndManager } from "./dnd-wrapper";
import { downloadFile } from "./download";
import { FileViewer } from "./file-viewer";
import type { FileTreeNode, RequestingTree } from "./requesting-tree";
import { openStateAtom, treeAtom } from "./state";
import { PYTHON_CODE_FOR_FILE_TYPE } from "./types";
import {
  FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE,
  useFileExplorerUpload,
} from "./upload";

const hiddenFilesState = atomWithStorage(
  "marimo:showHiddenFiles",
  true,
  jotaiJsonStorage,
  {
    getOnInit: true,
  },
);

interface FileExplorerContextValue {
  tree: RequestingTree;
  uploadFiles: (destinationPath: FilePath) => void;
  externalDropDestinationPath: FilePath | null;
}

const RequestingTreeContext =
  React.createContext<FileExplorerContextValue | null>(null);

export const FileExplorer: React.FC<{
  height: number;
  externalDropDestinationPath?: FilePath | null;
}> = ({ height, externalDropDestinationPath = null }) => {
  const treeRef = useRef<TreeApi<FileTreeNode>>(null);
  const dndManager = useTreeDndManager();
  const [tree] = useAtom(treeAtom);
  const [data, setData] = useState<FileTreeNode[]>([]);
  const [openFile, setOpenFile] = useState<FileTreeNode | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<{
    id: string;
    path: FilePath;
  } | null>(null);
  const [showHiddenFiles, setShowHiddenFiles] =
    useAtom<boolean>(hiddenFilesState);
  // Keep external state to remember which folders are open when this
  // component is unmounted.
  const [openState, setOpenState] = useAtom(openStateAtom);

  const refreshUploadDestination = useEvent((destinationPath: FilePath) => {
    return tree.refreshPath(destinationPath);
  });

  const uploadDestinationRef = useRef<FilePath>("" as FilePath);
  const { getInputProps: getUploadInputProps, open: openUploadPicker } =
    useFileExplorerUpload({
      noClick: true,
      noDrag: true,
      noKeyboard: true,
      destinationPath: () => uploadDestinationRef.current,
      getDestinationLabel: (path) => getUploadDestinationLabel(tree, path),
      refreshDestination: refreshUploadDestination,
    });
  const handleUploadFiles = useEvent((destinationPath: FilePath) => {
    uploadDestinationRef.current = destinationPath;
    openUploadPicker();
  });

  const { openPrompt } = useImperativeModal();
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
        tree.createFolder(name, selectedFolder?.id ?? null);
      },
    });
  });

  const handleCreateFile = useEvent(async () => {
    openPrompt({
      title: "File name",
      onConfirm: async (name) => {
        tree.createFile({ name, parentId: selectedFolder?.id ?? null });
      },
    });
  });

  const handleCreateNotebook = useEvent(async () => {
    openPrompt({
      title: "Notebook name",
      onConfirm: async (name) => {
        tree.createFile({
          name,
          parentId: selectedFolder?.id ?? null,
          type: "notebook",
        });
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
  React.useEffect(() => {
    if (selectedFolder && !treeContainsId(visibleData, selectedFolder.id)) {
      setSelectedFolder(null);
    }
  }, [selectedFolder, visibleData]);
  const contextValue = React.useMemo<FileExplorerContextValue>(
    () => ({
      tree,
      uploadFiles: handleUploadFiles,
      externalDropDestinationPath,
    }),
    [tree, handleUploadFiles, externalDropDestinationPath],
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
            onOpenNotebook={
              tree.isPrimaryNode(openFile)
                ? (evt) => {
                    const path = tree.getPrimaryRelativePath(
                      openFile.path as FilePath,
                    );
                    if (path !== null) {
                      openMarimoNotebook(evt, path);
                    }
                  }
                : undefined
            }
            file={openFile}
          />
        </Suspense>
      </>
    );
  }

  return (
    <>
      <input
        data-testid="file-explorer-upload-input"
        {...getUploadInputProps()}
      />
      <Toolbar
        onRefresh={handleRefresh}
        onHidden={handleHiddenFilesToggle}
        showHiddenFiles={showHiddenFiles}
        onCreateFile={handleCreateFile}
        onCreateNotebook={handleCreateNotebook}
        onCreateFolder={handleCreateFolder}
        onCollapseAll={handleCollapseAll}
        uploadDestinationPath={
          selectedFolder?.path ?? tree.getPrimaryRootPath()
        }
        uploadDestinationLabel={getUploadDestinationLabel(
          tree,
          selectedFolder?.path ?? tree.getPrimaryRootPath(),
        )}
        onUpload={handleUploadFiles}
      />
      <RequestingTreeContext value={contextValue}>
        <Tree<FileTreeNode>
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
          disableDrag={(node) => node.isRoot}
          disableDrop={({ parentNode, dragNodes }) =>
            dragNodes.some((node) => node.data.isRoot) ||
            (parentNode ? !parentNode.data.isDirectory : false)
          }
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
              setSelectedFolder(null);
              return;
            }
            if (first.data.isDirectory) {
              setSelectedFolder({
                id: first.id,
                path: first.data.path as FilePath,
              });
              return;
            }
            setSelectedFolder(null);
            setOpenFile(first.data);
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
  showHiddenFiles: boolean;
  onCreateFile: () => void;
  onCreateNotebook: () => void;
  onCreateFolder: () => void;
  onCollapseAll: () => void;
  uploadDestinationPath: FilePath;
  uploadDestinationLabel: string;
  onUpload: (destinationPath: FilePath) => void;
}

const Toolbar = ({
  onRefresh,
  onHidden,
  showHiddenFiles,
  onCreateFile,
  onCreateNotebook,
  onCreateFolder,
  onCollapseAll,
  uploadDestinationPath,
  uploadDestinationLabel,
  onUpload,
}: ToolbarProps) => {
  const uploadLabel = `Upload files to ${uploadDestinationLabel}`;

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
      <Tooltip content={uploadLabel}>
        <Button
          data-testid="file-explorer-upload-button"
          aria-label={uploadLabel}
          onClick={() => onUpload(uploadDestinationPath)}
          variant="text"
          size="xs"
        >
          <UploadIcon size={16} />
        </Button>
      </Tooltip>
      <RefreshIconButton
        data-testid="file-explorer-refresh-button"
        onClick={onRefresh}
      />
      <VisibilityToggleButton
        data-testid="file-explorer-hidden-files-button"
        isVisible={showHiddenFiles}
        onToggle={onHidden}
        showTooltip="Show hidden files"
        hideTooltip="Hide hidden files"
      />
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
  node: NodeApi<FileTreeNode>;
  onOpenMarimoFile: (
    evt: Pick<Event, "stopPropagation" | "preventDefault">,
  ) => void;
}) => {
  const label = (
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
      {node.data.isMarimoFile && node.data.isPrimaryRoot && !isWasm() && (
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

  return node.data.isRoot ? (
    <Tooltip content={node.data.path}>{label}</Tooltip>
  ) : (
    label
  );
};

const Node = ({ node, style, dragHandle }: NodeRendererProps<FileTreeNode>) => {
  const { openFile } = useRequestClient();
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

  const fileExplorer = use(RequestingTreeContext);
  const tree = fileExplorer?.tree;
  const isExternalDropTarget =
    node.data.isDirectory &&
    fileExplorer?.externalDropDestinationPath === node.data.path;

  const handleOpenMarimoFile = async (
    evt: Pick<Event, "stopPropagation" | "preventDefault">,
  ) => {
    const path = tree?.getPrimaryRelativePath(node.data.path as FilePath);
    if (path !== null && path !== undefined) {
      openMarimoNotebook(evt, path);
    }
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
      {...(node.data.isDirectory
        ? { [FILE_EXPLORER_DIRECTORY_PATH_ATTRIBUTE]: node.data.path }
        : {})}
      className={cn(
        "flex items-center cursor-pointer ml-1 text-muted-foreground whitespace-nowrap group",
      )}
      draggable={!node.data.isRoot}
      onClick={(evt) => {
        evt.stopPropagation();
        if (node.data.isDirectory) {
          node.select();
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
          node.isSelected &&
            "bg-accent/60 hover:bg-accent/60 text-accent-foreground",
          isExternalDropTarget &&
            "bg-primary/15 hover:bg-primary/15 text-accent-foreground ring-1 ring-inset ring-primary",
        )}
      >
        {node.data.isRoot ? (
          <FolderRootIcon
            className="w-5 h-5 shrink-0 mr-2 text-primary"
            strokeWidth={1.5}
          />
        ) : node.data.isMarimoFile ? (
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
            <DropdownMenuItem
              onSelect={() => node.select()}
              data-testid="file-explorer-open-file-menu-item"
            >
              <ViewIcon className={MENU_ITEM_ICON_CLASS} />
              Open file
            </DropdownMenuItem>
          )}
          {!node.data.isDirectory && !isWasm() && (
            <DropdownMenuItem
              onSelect={() => {
                openFile({ path: node.data.path });
              }}
              data-testid="file-explorer-open-external-menu-item"
            >
              <ExternalLinkIcon className={MENU_ITEM_ICON_CLASS} />
              Open file in external editor
            </DropdownMenuItem>
          )}
          {node.data.isDirectory && (
            <>
              <DropdownMenuItem
                onSelect={() => handleCreateNotebook()}
                data-testid="file-explorer-create-notebook-menu-item"
              >
                <MarimoPlusIcon className={MENU_ITEM_ICON_CLASS} />
                Create notebook
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => handleCreateFile()}
                data-testid="file-explorer-create-file-menu-item"
              >
                <FilePlus2Icon className={MENU_ITEM_ICON_CLASS} />
                Create file
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() => handleCreateFolder()}
                data-testid="file-explorer-create-folder-menu-item"
              >
                <FolderPlusIcon className={MENU_ITEM_ICON_CLASS} />
                Create folder
              </DropdownMenuItem>
              <DropdownMenuItem
                onSelect={() =>
                  fileExplorer?.uploadFiles(node.data.path as FilePath)
                }
                data-testid="file-explorer-upload-files-menu-item"
              >
                <UploadIcon className={MENU_ITEM_ICON_CLASS} />
                Upload files here
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          {!node.data.isRoot && (
            <>
              <RenameMenuItem
                onSelect={() => node.edit()}
                testId="file-explorer-rename-menu-item"
              />
              <DuplicateMenuItem
                onSelect={handleDuplicate}
                testId="file-explorer-duplicate-menu-item"
              />
            </>
          )}
          <DropdownMenuItem
            onSelect={async () => {
              await copyToClipboard(node.data.path);
              toast({ title: "Copied to clipboard" });
            }}
            data-testid="file-explorer-copy-path-menu-item"
          >
            <ListTreeIcon className={MENU_ITEM_ICON_CLASS} />
            Copy path
          </DropdownMenuItem>
          {tree && node.data.isPrimaryRoot && !node.data.isRoot && (
            <DropdownMenuItem
              onSelect={async () => {
                const path = tree.getPrimaryRelativePath(
                  node.data.path as FilePath,
                );
                if (path !== null) {
                  await copyToClipboard(path);
                  toast({ title: "Copied to clipboard" });
                }
              }}
              data-testid="file-explorer-copy-relative-path-menu-item"
            >
              <ListTreeIcon className={MENU_ITEM_ICON_CLASS} />
              Copy relative path
            </DropdownMenuItem>
          )}
          {!node.data.isRoot && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={() => {
                  const { path } = node.data;
                  const pythonCode = PYTHON_CODE_FOR_FILE_TYPE[fileType](path);
                  handleInsertCode(pythonCode);
                }}
                data-testid="file-explorer-insert-snippet-menu-item"
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
                data-testid="file-explorer-copy-snippet-menu-item"
              >
                <BracesIcon className={MENU_ITEM_ICON_CLASS} />
                Copy snippet for reading file
              </DropdownMenuItem>
            </>
          )}
          {node.data.isMarimoFile && node.data.isPrimaryRoot && !isWasm() && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={handleOpenMarimoFile}
                data-testid="file-explorer-open-notebook-menu-item"
              >
                <PlaySquareIcon className={MENU_ITEM_ICON_CLASS} />
                Open notebook
              </DropdownMenuItem>
            </>
          )}
          {!node.data.isDirectory && !disableFileDownloads && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onSelect={async () => {
                  await downloadFile(node.data.path, node.data.name);
                }}
                data-testid="file-explorer-download-menu-item"
              >
                <DownloadIcon className={MENU_ITEM_ICON_CLASS} />
                Download
              </DropdownMenuItem>
            </>
          )}
          {!node.data.isRoot && (
            <>
              <DropdownMenuSeparator />
              <DeleteMenuItem
                onSelect={handleDeleteFile}
                testId="file-explorer-delete-menu-item"
              />
            </>
          )}
        </FileActionsDropdown>
      </span>
    </div>
  );
};

const FolderArrow = ({ node }: { node: NodeApi<FileTreeNode> }) => {
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

export function getUploadDestinationLabel(
  tree: RequestingTree,
  destinationPath: FilePath,
): string {
  return tree.getDisplayPath(destinationPath);
}

export function filterHiddenTree(
  list: FileTreeNode[],
  showHidden: boolean,
): FileTreeNode[] {
  if (showHidden) {
    return list;
  }

  const out: FileTreeNode[] = [];
  for (const item of list) {
    if (!item.isRoot && isDirectoryOrFileHidden(item.name)) {
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

function treeContainsId(list: FileTreeNode[], id: string): boolean {
  return list.some(
    (item) =>
      item.id === id ||
      (item.children ? treeContainsId(item.children, id) : false),
  );
}
