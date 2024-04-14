/* Copyright 2024 Marimo. All rights reserved. */
import {
  getWorkspaceFiles,
  getRecentFiles,
  getRunningNotebooks,
  shutdownSession,
} from "@/core/network/requests";
import { combineAsyncData, useAsyncData } from "@/hooks/useAsyncData";
import React, { Suspense, useState } from "react";
import { Spinner } from "../icons/spinner";
import { ExternalLinkIcon, PowerOffIcon } from "lucide-react";
import { ShutdownButton } from "../editor/controls/shutdown-button";
import {
  SessionId,
  generateSessionId,
  getSessionId,
  isSessionId,
} from "@/core/kernel/session";
import { useInterval } from "@/hooks/useInterval";
import { cn } from "@/utils/cn";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "@/components/ui/alert-dialog";
import { assertExists } from "@/utils/assertExists";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { RunningNotebooksResponse } from "@/core/network/types";

function tabTarget(path: string) {
  // Consistent tab target so we open in the same tab when clicking on the same notebook
  return `${getSessionId()}-${encodeURIComponent(path)}`;
}

export const HomePage: React.FC = () => {
  const fileResponse = useAsyncData(async () => {
    const [workspace, recents] = await Promise.all([
      getWorkspaceFiles(),
      getRecentFiles(),
    ]);
    return { workspace, recents };
  }, []);

  const [nonce, setNonce] = useState(0);
  useInterval(
    () => {
      setNonce((nonce) => nonce + 1);
    },
    // Refresh every 10 seconds, or when the document becomes visible
    { delayMs: 10_000, whenVisible: true },
  );

  const runningResponse = useAsyncData(async () => {
    return getRunningNotebooks();
  }, [nonce]);

  const error = fileResponse.error || runningResponse.error;
  if (error) {
    throw error;
  }

  const data = combineAsyncData(fileResponse, runningResponse).data;
  if (fileResponse.loading || !data) {
    return <Spinner centered={true} size="xlarge" />;
  }

  const [{ workspace, recents }, running] = data;

  const runningNotebooks = new Map(
    running.files.flatMap((file) =>
      file.initializationId && file.sessionId
        ? [
            [
              file.path,
              {
                sessionId: file.sessionId,
                initializationId: file.initializationId,
              },
            ],
          ]
        : [],
    ),
  );

  return (
    <Suspense>
      {/*<GridBackground />*/}
      <div className="absolute top-3 right-5">
        <ShutdownButton
          description={`This will shutdown the notebook server and terminate all running notebooks (${running.files.length}). You'll lose all data that's in memory.`}
        />
      </div>
      <div className="flex flex-col gap-8 max-w-5xl container pt-10 pb-20 z-10">
        <img src="/logo.png" alt="Marimo Logo" className="w-64 mb-4" />
        <CreateNewNotebook />
        <NotebookList
          header="Running notebooks"
          files={running.files}
          runningNotebooks={runningNotebooks}
          setRunningNotebooks={runningResponse.setData}
        />
        <NotebookList
          header="Recent notebooks"
          files={recents.files}
          runningNotebooks={runningNotebooks}
          setRunningNotebooks={runningResponse.setData}
        />
        <NotebookList
          header="All notebooks"
          files={workspace.files}
          runningNotebooks={runningNotebooks}
          setRunningNotebooks={runningResponse.setData}
        />
        {/* <NotebookFromOrCodeUrl /> */}
      </div>
    </Suspense>
  );
};

const NotebookList: React.FC<{
  header: string;
  files: Array<{
    name: string;
    path: string;
    sessionId?: string;
    initializationId?: string;
  }>;
  runningNotebooks: Map<
    string,
    {
      sessionId: SessionId;
      initializationId: string;
    }
  >;
  setRunningNotebooks: (data: RunningNotebooksResponse) => void;
}> = ({ header, files, runningNotebooks, setRunningNotebooks }) => {
  const { openConfirm, closeModal } = useImperativeModal();

  if (files.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      <Header>{header}</Header>
      <div
        className="flex flex-col divide-y divide-[var(--slate-3)] border rounded overflow-hidden
        max-h-[48rem] overflow-y-auto shadow-sm bg-background
        "
      >
        {files.map((file) => {
          // If path is a sessionId, then it has not been saved yet
          // We want to keep the sessionId in this case
          const isNewNotebook = isSessionId(file.path);
          const href = isNewNotebook
            ? `/?file=${file.initializationId}&session_id=${file.path}`
            : `/?file=${file.path}`;

          return (
            <a
              className="py-2 px-4 hover:bg-[var(--blue-2)] hover:text-primary transition-all duration-300 cursor-pointer group relative"
              key={file.path}
              href={href}
              target={tabTarget(file.initializationId || file.path)}
            >
              <div className="flex flex-col justify-between">
                <span>{file.name}</span>
                <p
                  title={file.path}
                  className="text-sm text-muted-foreground
                overflow-hidden whitespace-nowrap overflow-ellipsis
              "
                >
                  {file.path}
                </p>
              </div>
              <div className="absolute right-16 top-0 bottom-0 flex items-center">
                {runningNotebooks.has(file.path) && (
                  <Tooltip content="Shutdown">
                    <Button
                      size={"xs"}
                      variant="outline"
                      className="m-0 opacity-80 hover:opacity-100 hover:bg-accent text-destructive border-destructive hover:border-destructive hover:text-destructive bg-background hover:bg-[var(--red-1)]"
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
                                const ids = runningNotebooks.get(file.path);
                                assertExists(ids);
                                shutdownSession({
                                  sessionId: ids.sessionId,
                                }).then((response) => {
                                  setRunningNotebooks(response);
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
                      <PowerOffIcon size={16} />
                    </Button>
                  </Tooltip>
                )}
              </div>
              <div
                className={cn(
                  "absolute right-8 top-0 bottom-0 rounded-lg flex items-center justify-center text-muted-foreground text-primary",
                )}
              >
                <ExternalLinkIcon
                  size={24}
                  className="absolute group-hover:opacity-100 opacity-0 transition-all duration-300"
                />
              </div>
            </a>
          );
        })}
      </div>
    </div>
  );
};

const Header: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <h2 className="text-xl font-semibold text-muted-foreground">{children}</h2>
  );
};

const CreateNewNotebook: React.FC = () => {
  const sessionId = generateSessionId();
  const initializationId = `__new__${sessionId}`;
  return (
    <a
      className="relative rounded-lg p-6 group
      text-primary hover:bg-[var(--blue-2)] shadow-smAccent border
      transition-all duration-300 cursor-pointer
      "
      href={`/?file=${initializationId}`}
      target={tabTarget(initializationId)}
    >
      <h2 className="text-lg font-semibold">Create a new notebook</h2>
      <div className="group-hover:opacity-100 opacity-0 absolute right-5 top-0 bottom-0 rounded-lg flex items-center justify-center transition-all duration-300">
        <ExternalLinkIcon size={24} />
      </div>
    </a>
  );
};

// const NotebookFromOrCodeUrl: React.FC = () => {
//   return (
//     <div className="flex flex-col gap-2">
//       <h3 className="text-lg font-semibold">
//         Open a notebook from URL or paste code
//       </h3>
//       <Input
//         className="h-12 px-4 border-border"
//         type="text"
//         placeholder="Enter URL"
//       />
//     </div>
//   );
// };
