/* Copyright 2024 Marimo. All rights reserved. */
import {
  getWorkspaceFiles,
  getRecentFiles,
  getRunningNotebooks,
  shutdownSession,
} from "@/core/network/requests";
import { combineAsyncData, useAsyncData } from "@/hooks/useAsyncData";
import type React from "react";
import { Suspense, useContext, useEffect, useRef, useState } from "react";
import { Spinner } from "../icons/spinner";
import {
  BookTextIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsDownUpIcon,
  ClockIcon,
  ExternalLinkIcon,
  PlayCircleIcon,
  PowerOffIcon,
  RefreshCcwIcon,
  SearchIcon,
} from "lucide-react";
import { ShutdownButton } from "../editor/controls/shutdown-button";
import {
  type SessionId,
  getSessionId,
  isSessionId,
} from "@/core/kernel/session";
import { useInterval } from "@/hooks/useInterval";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { assertExists } from "@/utils/assertExists";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import type { FileInfo, MarimoFile } from "@/core/network/types";
import { ConfigButton } from "../app-config/app-config-button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { MarkdownIcon } from "@/components/editor/cell/code/icons";
import { asURL } from "@/utils/url";
import { timeAgo } from "@/utils/dates";
import {
  type NodeApi,
  type NodeRendererProps,
  Tree,
  type TreeApi,
} from "react-arborist";
import { cn } from "@/utils/cn";
import {
  type FileType,
  guessFileType,
  FILE_TYPE_ICONS,
} from "../editor/file-tree/types";
import { useAtom, useSetAtom } from "jotai";
import {
  expandedFoldersAtom,
  includeMarkdownAtom,
  RunningNotebooksContext,
  WorkspaceRootContext,
} from "../home/state";
import { Maps } from "@/utils/maps";
import { Input } from "../ui/input";
import { Paths } from "@/utils/paths";
import { ErrorBoundary } from "../editor/boundary/ErrorBoundary";
import { Banner } from "@/plugins/impl/common/error-banner";
import { prettyError } from "@/utils/errors";
import { newNotebookURL } from "@/utils/urls";
import {
  Header,
  OpenTutorialDropDown,
  ResourceLinks,
} from "../home/components";

function tabTarget(path: string) {
  // Consistent tab target so we open in the same tab when clicking on the same notebook
  return `${getSessionId()}-${encodeURIComponent(path)}`;
}

const HomePage: React.FC = () => {
  const [nonce, setNonce] = useState(0);

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
      <RunningNotebooksContext.Provider
        value={{
          runningNotebooks: running,
          setRunningNotebooks: runningResponse.setData,
        }}
      >
        <div className="absolute top-3 right-5 flex gap-3 z-50">
          <OpenTutorialDropDown />
          <ConfigButton showAppConfig={false} />
          <ShutdownButton
            description={`This will shutdown the notebook server and terminate all running notebooks (${running.size}). You'll lose all data that's in memory.`}
          />
        </div>
        <div className="flex flex-col gap-6 max-w-6xl container pt-5 pb-20 z-10">
          <img src="logo.png" alt="marimo logo" className="w-48 mb-2" />
          <CreateNewNotebook />
          <ResourceLinks />
          <NotebookList
            header={<Header Icon={PlayCircleIcon}>Running notebooks</Header>}
            files={[...running.values()]}
          />
          <NotebookList
            header={<Header Icon={ClockIcon}>Recent notebooks</Header>}
            files={recents.files}
          />
          <ErrorBoundary>
            <WorkspaceNotebooks />
          </ErrorBoundary>
        </div>
      </RunningNotebooksContext.Provider>
    </Suspense>
  );
};

const WorkspaceNotebooks: React.FC = () => {
  const [includeMarkdown, setIncludeMarkdown] = useAtom(includeMarkdownAtom);
  const [searchText, setSearchText] = useState("");
  const workspaceResponse = useAsyncData(
    () => getWorkspaceFiles({ includeMarkdown }),
    [includeMarkdown],
  );

  if (workspaceResponse.error) {
    return (
      <Banner kind="danger" className="rounded p-4">
        {prettyError(workspaceResponse.error)}
      </Banner>
    );
  }

  if (workspaceResponse.loading || !workspaceResponse.data) {
    return <Spinner centered={true} size="xlarge" className="mt-6" />;
  }

  const workspace = workspaceResponse.data;

  return (
    <WorkspaceRootContext.Provider value={workspace.root}>
      <div className="flex flex-col gap-2">
        <Header
          Icon={BookTextIcon}
          control={
            <div className="flex items-center gap-2">
              <Input
                id="search"
                value={searchText}
                icon={<SearchIcon size={13} />}
                onChange={(e) => setSearchText(e.target.value)}
                placeholder="Search"
                className="mb-0 border-border"
              />
              <CollapseAllButton />
              <Checkbox
                data-testid="include-markdown-checkbox"
                id="include-markdown"
                checked={includeMarkdown}
                onCheckedChange={(checked) =>
                  setIncludeMarkdown(Boolean(checked))
                }
              />
              <Label htmlFor="include-markdown">Include markdown</Label>
            </div>
          }
        >
          Workspace
          <RefreshCcwIcon
            className="w-4 h-4 ml-1 cursor-pointer opacity-70 hover:opacity-100"
            onClick={() => workspaceResponse.reload()}
          />
          {workspaceResponse.loading && <Spinner size="small" />}
        </Header>
        <div className="flex flex-col divide-y divide-[var(--slate-3)] border rounded overflow-hidden max-h-[48rem] overflow-y-auto shadow-sm bg-background">
          <NotebookFileTree searchText={searchText} files={workspace.files} />
        </div>
      </div>
    </WorkspaceRootContext.Provider>
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
  const ref = useRef<TreeApi<FileInfo>>();

  useEffect(() => {
    // If empty, collapse all
    if (openStateIsEmpty) {
      ref.current?.closeAll();
    }
  }, [openStateIsEmpty]);

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
      padding={5}
      rowHeight={35}
      indent={15}
      overscanCount={1000}
      // Hide the drop cursor
      renderCursor={() => null}
      // Disable interactions
      disableDrop={true}
      disableDrag={true}
      disableEdit={true}
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
  const iconEl = <Icon className="w-5 h-5 flex-shrink-0" strokeWidth={1.5} />;
  const root = useContext(WorkspaceRootContext);

  const renderItem = () => {
    const itemClassName =
      "flex items-center pl-1 cursor-pointer hover:bg-accent/50 hover:text-accent-foreground rounded-l flex-1 overflow-hidden h-full pr-3 gap-2";
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

    return (
      <a
        className={itemClassName}
        href={asURL(`?file=${relativePath}`).toString()}
        target={tabTarget(relativePath)}
      >
        {iconEl}
        <span className="flex-1 overflow-hidden text-ellipsis">
          {node.data.name}
          {isMarkdown && <MarkdownIcon className="ml-2 inline opacity-80" />}
        </span>
        <SessionShutdownButton filePath={relativePath} />
        <ExternalLinkIcon
          size={20}
          className="group-hover:opacity-100 opacity-0 text-primary"
        />
      </a>
    );
  };

  return (
    <div
      style={style}
      className={cn(
        "flex items-center cursor-pointer ml-1 text-muted-foreground whitespace-nowrap group h-full",
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

const NotebookList: React.FC<{
  header: React.ReactNode;
  files: MarimoFile[];
}> = ({ header, files }) => {
  if (files.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      {header}
      <div className="flex flex-col divide-y divide-[var(--slate-3)] border rounded overflow-hidden max-h-[48rem] overflow-y-auto shadow-sm bg-background">
        {files.map((file) => {
          return <MarimoFileComponent key={file.path} file={file} />;
        })}
      </div>
    </div>
  );
};

const MarimoFileComponent = ({
  file,
}: {
  file: MarimoFile;
}) => {
  // If path is a sessionId, then it has not been saved yet
  // We want to keep the sessionId in this case
  const isNewNotebook = isSessionId(file.path);
  const href = isNewNotebook
    ? asURL(`?file=${file.initializationId}&session_id=${file.path}`)
    : asURL(`?file=${file.path}`);

  const isMarkdown = file.path.endsWith(".md");

  return (
    <a
      className="py-1.5 px-4 hover:bg-[var(--blue-2)] hover:text-primary transition-all duration-300 cursor-pointer group relative flex gap-4 items-center"
      key={file.path}
      href={href.toString()}
      target={tabTarget(file.initializationId || file.path)}
    >
      <div className="flex flex-col justify-between flex-1">
        <span className="flex items-center gap-2">
          {file.name}
          {isMarkdown && (
            <span className="opacity-80">
              <MarkdownIcon />
            </span>
          )}
        </span>
        <p
          title={file.path}
          className="text-sm text-muted-foreground overflow-hidden whitespace-nowrap overflow-ellipsis"
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
            size={20}
            className="group-hover:opacity-100 opacity-0 transition-all duration-300 text-primary"
          />
        </div>
        {!!file.lastModified && (
          <div className="text-xs text-muted-foreground opacity-80">
            {timeAgo(file.lastModified * 1000)}
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
  const { runningNotebooks, setRunningNotebooks } = useContext(
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
        className="opacity-80 hover:opacity-100 hover:bg-accent text-destructive border-destructive hover:border-destructive hover:text-destructive bg-background hover:bg-[var(--red-1)]"
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
                onClick={(e) => {
                  const ids = runningNotebooks.get(filePath);
                  assertExists(ids);
                  shutdownSession({
                    sessionId: ids.sessionId as SessionId,
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

const CreateNewNotebook: React.FC = () => {
  const url = newNotebookURL();
  return (
    <a
      className="relative rounded-lg p-6 group
      text-primary hover:bg-[var(--blue-2)] shadow-mdSolid shadow-accent border bg-[var(--blue-1)]
      transition-all duration-300 cursor-pointer
      "
      href={url}
      target="_blank"
      rel="noreferrer"
    >
      <h2 className="text-lg font-semibold">Create a new notebook</h2>
      <div className="group-hover:opacity-100 opacity-0 absolute right-5 top-0 bottom-0 rounded-lg flex items-center justify-center transition-all duration-300">
        <ExternalLinkIcon size={24} />
      </div>
    </a>
  );
};

export default HomePage;
