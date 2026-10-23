/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom, useSetAtom } from "jotai";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsDownUpIcon,
  ExternalLinkIcon,
  PlusIcon,
  PowerOffIcon,
  RefreshCcwIcon,
  SearchIcon,
} from "lucide-react";
import type React from "react";
import { Suspense, use, useEffect, useMemo, useRef, useState } from "react";
import {
  type NodeApi,
  type NodeRendererProps,
  Tree,
  type TreeApi,
} from "react-arborist";
import { useLocale } from "react-aria";
import useEvent from "react-use-event-hook";
import { MarkdownIcon } from "@/components/editor/cell/code/icons";
import {
  FILE_ICON as FILE_TYPE_ICONS,
  type FileIconType as FileType,
  guessFileIconType as guessFileType,
} from "@/components/editor/file-tree/file-icons";
import { FileNameInput } from "@/components/editor/file-tree/file-name-input";
import {
  DeleteMenuItem,
  DuplicateMenuItem,
  FileActionsDropdown,
  RenameMenuItem,
  useFileOperations,
  useNotebookFileActions,
} from "@/components/editor/file-tree/file-operations";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { DropdownMenuSeparator } from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { getSessionId, isSessionId } from "@/core/kernel/session";
import { useRequestClient } from "@/core/network/requests";
import type { FileInfo, MarimoFile } from "@/core/network/types";
import { combineAsyncData, useAsyncData } from "@/hooks/useAsyncData";
import { useInterval } from "@/hooks/useInterval";
import { Banner } from "@/plugins/impl/common/error-banner";
import { assertExists } from "@/utils/assertExists";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/dates";
import { prettyError } from "@/utils/errors";
import { Maps } from "@/utils/maps";
import { Paths } from "@/utils/paths";
import { asURL } from "@/utils/url";
import { newNotebookURL } from "@/utils/urls";
import { ConfigButton } from "../app-config/app-config-button";
import { ErrorBoundary } from "../editor/boundary/ErrorBoundary";
import { ShutdownButton } from "../editor/controls/shutdown-button";
import {
  OpenTutorialDropDown,
  ResourceLinks,
  TruncatedWorkspaceBanner,
} from "../home/components";
import {
  expandedFoldersAtom,
  includeMarkdownAtom,
  RunningNotebooksContext,
  WorkspaceContext,
} from "../home/state";
import { Spinner } from "../icons/spinner";
import { Input } from "../ui/input";

function tabTarget(path: string) {
  // Consistent tab target so we open in the same tab when clicking on the same notebook
  return `${getSessionId()}-${encodeURIComponent(path)}`;
}

const NOTEBOOK_TAB_CLASS =
  "-mb-px rounded-none border-b-2 border-transparent px-1 py-3 text-(--gray-11) transition-colors hover:text-foreground focus-visible:ring-inset focus-visible:ring-offset-0 data-[state=active]:border-(--green-11) data-[state=active]:bg-transparent data-[state=active]:text-(--green-11) data-[state=active]:shadow-none";

const HomePage: React.FC = () => {
  const [nonce, setNonce] = useState(0);
  const { getRecentFiles, getRunningNotebooks } = useRequestClient();

  const recentsResponse = useAsyncData(() => getRecentFiles(), []);

  useInterval(
    () => {
      setNonce((nonce) => nonce + 1);
    },
    // Refresh every 10 seconds, or when the document becomes visible
    { delayMs: 10_000, whenVisible: true },
  );

  const runningResponse = useAsyncData(async () => {
    const response = await getRunningNotebooks();
    return Maps.keyBy(response.files, (file) => file.path);
  }, [nonce]);

  const response = combineAsyncData(recentsResponse, runningResponse);

  if (response.error) {
    throw response.error;
  }

  const data = response.data;
  if (!data) {
    return <Spinner centered={true} size="xlarge" />;
  }

  const [recents, running] = data;

  return (
    <Suspense>
      <RunningNotebooksContext
        value={{
          runningNotebooks: running,
          setRunningNotebooks: runningResponse.setData,
        }}
      >
        <div className="min-h-screen bg-background">
          <header className="border-b border-border/60">
            <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-5 sm:px-10">
              <img src="logo.png" alt="marimo" className="w-28" />
              <div className="flex items-center gap-3">
                <ConfigButton showAppConfig={false} />
                <ShutdownButton
                  description={`This will shutdown the notebook server and terminate all running notebooks (${running.size}). You'll lose all data that's in memory.`}
                />
              </div>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-5 py-8 sm:px-10 sm:py-10">
            <div className="mb-8">
              <h1 className="text-2xl font-semibold tracking-tight">
                Your notebooks
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                Pick up where you left off, or start something new.
              </p>
              <div className="mt-5 flex items-center gap-3">
                <CreateNewNotebook />
                <OpenTutorialDropDown />
              </div>
            </div>
            <Tabs defaultValue="workspace">
              <TabsList
                aria-label="Notebooks"
                className="mb-5 flex h-auto w-full justify-start gap-6 rounded-none border-b border-border/70 bg-transparent p-0"
              >
                <TabsTrigger value="workspace" className={NOTEBOOK_TAB_CLASS}>
                  Workspace
                </TabsTrigger>
                <TabsTrigger value="recent" className={NOTEBOOK_TAB_CLASS}>
                  Recent
                </TabsTrigger>
                <TabsTrigger value="running" className={NOTEBOOK_TAB_CLASS}>
                  Running
                  <span className="ml-1.5 text-xs font-normal tabular-nums text-(--gray-11)">
                    {running.size}
                  </span>
                </TabsTrigger>
              </TabsList>
              <TabsContent
                value="workspace"
                forceMount={true}
                className="mt-0 data-[state=inactive]:hidden"
              >
                <ErrorBoundary>
                  <WorkspaceNotebooks
                    onRefreshRecents={recentsResponse.refetch}
                  />
                </ErrorBoundary>
              </TabsContent>
              <TabsContent value="recent" className="mt-0">
                <NotebookList
                  files={recents.files}
                  emptyMessage="Notebooks you open will appear here."
                />
              </TabsContent>
              <TabsContent value="running" className="mt-0">
                <NotebookList
                  files={[...running.values()]}
                  emptyMessage="No notebooks are running."
                />
              </TabsContent>
            </Tabs>
            <ResourceLinks />
          </main>
        </div>
      </RunningNotebooksContext>
    </Suspense>
  );
};

const WorkspaceNotebooks: React.FC<{ onRefreshRecents: () => void }> = ({
  onRefreshRecents,
}) => {
  const { getWorkspaceFiles } = useRequestClient();
  const [includeMarkdown, setIncludeMarkdown] = useAtom(includeMarkdownAtom);
  const [searchText, setSearchText] = useState("");
  const {
    isPending,
    data: workspace,
    error,
    isFetching,
    refetch,
  } = useAsyncData(
    () => getWorkspaceFiles({ includeMarkdown }),
    [includeMarkdown],
  );

  // Fire-and-forget refresh of both the workspace tree and the "Recent
  // notebooks" list — file mutations on the workspace tree can affect both,
  // so we invalidate them together rather than having two refresh triggers.
  const refreshWorkspace = useEvent(() => {
    refetch();
    onRefreshRecents();
  });

  const workspaceContextValue = useMemo(
    () => ({ root: workspace?.root ?? "", refreshWorkspace }),
    [workspace?.root, refreshWorkspace],
  );

  if (isPending) {
    return <Spinner centered={true} size="xlarge" className="mt-6" />;
  }

  if (error) {
    return (
      <Banner kind="danger" className="rounded p-4">
        {prettyError(error)}
      </Banner>
    );
  }

  return (
    <WorkspaceContext value={workspaceContextValue}>
      <div className="flex min-w-0 flex-col gap-4">
        {workspace.hasMore && (
          <TruncatedWorkspaceBanner fileCount={workspace.fileCount} />
        )}
        <div className="overflow-hidden rounded-lg border border-border/70 bg-background">
          <div className="flex flex-wrap items-center gap-3 border-b border-border/60 bg-muted/20 p-3">
            <div className="min-w-40 flex-1">
              <Input
                id="search"
                aria-label="Search workspace"
                value={searchText}
                icon={<SearchIcon size={15} />}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Find a notebook…"
                className="mb-0 h-9 rounded-md border-border/60 bg-background font-sans shadow-none hover:shadow-none focus-visible:shadow-none"
              />
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => refetch()}
              aria-label="Refresh workspace"
            >
              {isFetching ? (
                <Spinner size="small" />
              ) : (
                <RefreshCcwIcon className="w-4 h-4" />
              )}
            </Button>
            <CollapseAllButton />
            <div className="flex items-center gap-2">
              <Checkbox
                data-testid="include-markdown-checkbox"
                id="include-markdown"
                checked={includeMarkdown}
                onCheckedChange={(checked) =>
                  setIncludeMarkdown(Boolean(checked))
                }
              />
              <Label
                htmlFor="include-markdown"
                className="text-xs text-muted-foreground"
              >
                Include markdown
              </Label>
            </div>
          </div>
          <NotebookFileTree searchText={searchText} files={workspace.files} />
        </div>
      </div>
    </WorkspaceContext>
  );
};

const CollapseAllButton: React.FC = () => {
  const setOpenState = useSetAtom(expandedFoldersAtom);
  return (
    <Button
      variant="text"
      size="sm"
      className="h-fit hidden sm:flex"
      onClick={() => {
        setOpenState({});
      }}
    >
      <ChevronsDownUpIcon className="w-4 h-4 mr-1" />
      Collapse all
    </Button>
  );
};

const NotebookFileTree: React.FC<{
  files: FileInfo[];
  searchText?: string;
}> = ({ files, searchText }) => {
  const [openState, setOpenState] = useAtom(expandedFoldersAtom);
  const openStateIsEmpty = Object.keys(openState).length === 0;
  const ref = useRef<TreeApi<FileInfo>>(undefined);
  const { root, refreshWorkspace } = use(WorkspaceContext);
  const { renameFile } = useFileOperations({ root });

  useEffect(() => {
    // If empty, collapse all
    if (openStateIsEmpty) {
      ref.current?.closeAll();
    }
  }, [openStateIsEmpty]);

  const handleRename = useEvent(async (id: string, name: string) => {
    const node = ref.current?.get(id);
    if (!node) {
      toast({
        title: "Failed",
        description: `Node with id ${id} not found in the tree`,
      });
      return;
    }
    const result = await renameFile(node.data, name);
    if (result) {
      refreshWorkspace();
    }
  });

  if (files.length === 0) {
    return (
      <div className="flex flex-col px-5 py-10 items-center justify-center">
        <p className="text-center text-muted-foreground">
          No files in this workspace
        </p>
      </div>
    );
  }

  return (
    <Tree<FileInfo>
      ref={ref}
      width="100%"
      height={500}
      searchTerm={searchText}
      className="h-full"
      idAccessor={(data) => data.path}
      data={files}
      openByDefault={false}
      initialOpenState={openState}
      onToggle={async (id) => {
        const prevOpen = openState[id] ?? false;
        setOpenState({ ...openState, [id]: !prevOpen });
      }}
      onRename={async ({ id, name }) => {
        await handleRename(id, name);
      }}
      padding={5}
      rowHeight={44}
      indent={15}
      overscanCount={1000}
      // Hide the drop cursor
      renderCursor={() => null}
      // Disable interactions
      disableDrop={true}
      disableDrag={true}
      disableMultiSelection={true}
    >
      {Node}
    </Tree>
  );
};

const Node = ({ node, style }: NodeRendererProps<FileInfo>) => {
  const fileType: FileType = node.data.isDirectory
    ? "directory"
    : guessFileType(node.data.name);

  const Icon = FILE_TYPE_ICONS[fileType];
  const iconEl = (
    <Icon className="w-4 h-4 shrink-0 text-(--gray-11)" strokeWidth={1.5} />
  );
  const { root } = use(WorkspaceContext);
  const { runningNotebooks } = use(RunningNotebooksContext);

  const renderItem = () => {
    const itemClassName =
      "flex items-center pl-1 cursor-pointer hover:bg-(--sage-3) hover:text-foreground rounded-l flex-1 overflow-hidden h-full pr-3 gap-2";

    // Inline rename input; react-arborist flips `node.isEditing` when
    // `node.edit()` is called from the FileActions menu.
    if (node.isEditing) {
      return (
        <div className={itemClassName}>
          {iconEl}
          <FileNameInput node={node} />
        </div>
      );
    }

    if (node.data.isDirectory) {
      return (
        <span className={itemClassName}>
          {iconEl}
          {node.data.name}
        </span>
      );
    }

    const relativePath =
      node.data.path.startsWith(root) && Paths.isAbsolute(node.data.path)
        ? Paths.rest(node.data.path, root)
        : node.data.path;

    const isMarkdown =
      relativePath.endsWith(".md") || relativePath.endsWith(".qmd");
    const isRunning = runningNotebooks.has(relativePath);

    return (
      <a
        className={itemClassName}
        href={asURL(`?file=${encodeURIComponent(relativePath)}`).toString()}
        target={tabTarget(relativePath)}
      >
        {iconEl}
        <span className="flex-1 overflow-hidden text-ellipsis">
          {node.data.name}
          {isMarkdown && <MarkdownIcon className="ml-2 inline opacity-80" />}
        </span>

        <FileActions node={node} isRunning={isRunning} />
        {/*
          Trailing action slots. Using a fixed-width row here (rather than
          conditionally rendered inline elements) keeps every row's right
          edge aligned even though any individual slot may be empty.
        */}
        <div className="w-8 h-8 flex items-center justify-center shrink-0">
          <SessionShutdownButton filePath={relativePath} />
        </div>
        <ExternalLinkIcon
          size={20}
          className="group-hover:opacity-100 opacity-0 text-primary shrink-0"
        />
      </a>
    );
  };

  return (
    <div
      style={style}
      className={cn(
        "flex items-center cursor-pointer ml-1 text-sm text-foreground whitespace-nowrap group h-full",
      )}
      onClick={(evt) => {
        evt.stopPropagation();
        if (node.data.isDirectory) {
          node.toggle();
        }
      }}
    >
      <FolderArrow node={node} />
      {renderItem()}
    </div>
  );
};

const FileActions = ({
  node,
  isRunning,
}: {
  node: NodeApi<FileInfo>;
  isRunning: boolean;
}) => {
  const { root, refreshWorkspace } = use(WorkspaceContext);
  const { handleRename, handleDuplicate, handleDelete } =
    useNotebookFileActions({ node, root, onAfterChange: refreshWorkspace });

  const lockedReason = isRunning
    ? "Stop the notebook's kernel before renaming or deleting."
    : undefined;

  return (
    <FileActionsDropdown
      testId="workspace-more-button"
      buttonClassName="w-8 h-8 p-0 shrink-0"
      contentClassName="print:hidden w-fit min-w-[140px]"
      preventDefaultOnTrigger={true}
    >
      <RenameMenuItem
        onSelect={handleRename}
        disabled={isRunning}
        title={lockedReason}
      />
      <DuplicateMenuItem onSelect={handleDuplicate} />
      <DropdownMenuSeparator />
      <DeleteMenuItem
        onSelect={handleDelete}
        disabled={isRunning}
        title={lockedReason}
      />
    </FileActionsDropdown>
  );
};

const FolderArrow = ({ node }: { node: NodeApi<FileInfo> }) => {
  if (!node.data.isDirectory) {
    return <span className="w-5 h-5 shrink-0" />;
  }

  return node.isOpen ? (
    <ChevronDownIcon className="w-5 h-5 shrink-0" />
  ) : (
    <ChevronRightIcon className="w-5 h-5 shrink-0" />
  );
};

const NotebookList: React.FC<{
  files: MarimoFile[];
  emptyMessage: string;
}> = ({ files, emptyMessage }) => {
  return (
    <div className="flex max-h-[500px] min-h-40 min-w-0 flex-col divide-y divide-border/50 overflow-y-auto rounded-lg border border-border/60">
      {files.length === 0 && (
        <p className="px-4 py-6 text-sm text-muted-foreground">
          {emptyMessage}
        </p>
      )}
      {files.map((file) => {
        return <MarimoFileComponent key={file.path} file={file} />;
      })}
    </div>
  );
};

const MarimoFileComponent = ({ file }: { file: MarimoFile }) => {
  const { locale } = useLocale();

  // If path is a sessionId, then it has not been saved yet
  // We want to keep the sessionId in this case
  const isNewNotebook = isSessionId(file.path);
  const href = isNewNotebook
    ? asURL(
        `?file=${encodeURIComponent(file.initializationId ?? file.path)}&session_id=${file.path}`,
      )
    : asURL(`?file=${encodeURIComponent(file.path)}`);

  const isMarkdown = file.path.endsWith(".md");
  const Icon = FILE_TYPE_ICONS[guessFileType(file.name)];

  return (
    <a
      className="py-3 px-4 hover:bg-(--sage-3) transition-colors cursor-pointer group relative flex gap-3 items-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      key={file.path}
      href={href.toString()}
      target={tabTarget(file.initializationId || file.path)}
    >
      <Icon className="h-4 w-4 shrink-0 text-(--gray-11)" strokeWidth={1.5} />
      <div className="flex min-w-0 flex-col gap-1 flex-1">
        <span className="flex items-center gap-2 text-sm font-medium">
          <span className="truncate">{file.name}</span>
          {isMarkdown && (
            <span className="opacity-80">
              <MarkdownIcon />
            </span>
          )}
        </span>
        <p
          title={file.path}
          className="text-xs text-muted-foreground overflow-hidden whitespace-nowrap text-ellipsis"
        >
          {file.path}
        </p>
      </div>
      <div className="flex flex-col gap-1 items-end">
        <div className="flex gap-3 items-center">
          <div>
            <SessionShutdownButton filePath={file.path} />
          </div>
          <ExternalLinkIcon
            size={14}
            className="opacity-40 group-hover:opacity-100"
          />
        </div>
        {!!file.lastModified && (
          <div className="text-xs text-muted-foreground opacity-80">
            {timeAgo(file.lastModified * 1000, locale)}
          </div>
        )}
      </div>
    </a>
  );
};

const SessionShutdownButton: React.FC<{ filePath: string }> = ({
  filePath,
}) => {
  const { openConfirm, closeModal } = useImperativeModal();
  const { shutdownSession } = useRequestClient();
  const { runningNotebooks, setRunningNotebooks } = use(
    RunningNotebooksContext,
  );
  if (!runningNotebooks.has(filePath)) {
    return null;
  }
  return (
    <Tooltip content="Shutdown">
      <Button
        size={"icon"}
        variant="outline"
        aria-label="Shutdown notebook"
        className="border-transparent text-muted-foreground shadow-none hover:border-destructive hover:bg-(--red-1) hover:text-destructive"
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          openConfirm({
            title: "Shutdown",
            description:
              "This will terminate the Python kernel. You'll lose all data that's in memory.",
            variant: "destructive",
            confirmAction: (
              <AlertDialogDestructiveAction
                onClick={() => {
                  const ids = runningNotebooks.get(filePath);
                  assertExists(ids?.sessionId);
                  shutdownSession({
                    sessionId: ids.sessionId,
                  }).then((response) => {
                    setRunningNotebooks(
                      Maps.keyBy(response.files, (file) => file.path),
                    );
                  });
                  closeModal();
                  toast({
                    description: "Notebook has been shutdown.",
                  });
                }}
                aria-label="Confirm Shutdown"
              >
                Shutdown
              </AlertDialogDestructiveAction>
            ),
          });
        }}
      >
        <PowerOffIcon size={14} />
      </Button>
    </Tooltip>
  );
};

export const CreateNewNotebook: React.FC = () => {
  // Reusing a `__new__` key reattaches to an old session; rotate it per open
  const [url, setUrl] = useState(newNotebookURL);
  const rotateUrl = () => {
    const next = newNotebookURL();
    setUrl(next);
    return next;
  };
  const rotateDragPayload = (event: React.DragEvent<HTMLAnchorElement>) => {
    // The browser copies the href into the drag payload before this handler
    // runs, so the rotated URL must be written into the payload by hand
    const next = rotateUrl();
    event.dataTransfer.setData("text/uri-list", next);
    event.dataTransfer.setData("text/plain", next);
  };
  return (
    <Button
      asChild={true}
      size="sm"
      className="gap-2 rounded-md border-(--brand) bg-(--brand) text-(--brand-foreground) shadow-none hover:bg-(--brand-hover)"
    >
      <a
        href={url}
        target="_blank"
        rel="noreferrer"
        onClick={rotateUrl}
        onAuxClick={rotateUrl}
        onContextMenu={rotateUrl}
        onDragStart={rotateDragPayload}
      >
        <PlusIcon className="h-4 w-4" />
        New notebook
      </a>
    </Button>
  );
};

export default HomePage;
