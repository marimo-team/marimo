/* Copyright 2024 Marimo. All rights reserved. */
import {
  getWorkspaceFiles,
  getRecentFiles,
  getRunningNotebooks,
} from "@/core/network/requests";
import { combineAsyncData, useAsyncData } from "@/hooks/useAsyncData";
import React, { Suspense, useState } from "react";
import { Spinner } from "../icons/spinner";
import { FilePlus2Icon, ExternalLinkIcon, Loader2Icon } from "lucide-react";
import { ShutdownButton } from "../editor/controls/shutdown-button";
import { getSessionId } from "@/core/kernel/session";
import { useInterval } from "@/hooks/useInterval";
import { cn } from "@/utils/cn";

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

  const runningNotebooks = new Set(running.files.map((file) => file.path));

  return (
    <Suspense>
      {/*<GridBackground />*/}
      <div className="absolute top-3 right-5">
        <ShutdownButton />
      </div>
      <div className="flex flex-col gap-8 max-w-5xl container pt-10 pb-20 z-10">
        <img src="/logo.png" alt="Marimo Logo" className="w-64 mb-4" />
        <CreateNewNotebook />
        <NotebookList
          header="Running notebooks"
          files={running.files}
          runningNotebooks={runningNotebooks}
        />
        <NotebookList
          header="Recent notebooks"
          files={recents.files}
          runningNotebooks={runningNotebooks}
        />
        <NotebookList
          header="All notebooks"
          files={workspace.files}
          runningNotebooks={runningNotebooks}
        />
        {/* <NotebookFromOrCodeUrl /> */}
      </div>
    </Suspense>
  );
};

const NotebookList: React.FC<{
  header: string;
  files: Array<{ name: string; path: string }>;
  runningNotebooks: Set<string>;
}> = ({ header, files, runningNotebooks }) => {
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
        {files.map((file) => (
          <a
            className="py-2 px-4 hover:bg-[var(--blue-2)] hover:text-primary transition-all duration-300 cursor-pointer group relative"
            key={file.path}
            href={`/?file=${file.path}`}
            target={tabTarget(file.path)}
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
            <div
              className={cn(
                "absolute right-8 top-0 bottom-0 rounded-lg flex items-center justify-center text-muted-foreground text-primary",
              )}
            >
              {runningNotebooks.has(file.path) && (
                <div className="absolute transition-all duration-300 opacity-100 group-hover:opacity-0">
                  <Loader2Icon size={24} className="animate-spin" />
                </div>
              )}
              <ExternalLinkIcon
                size={24}
                className="absolute group-hover:opacity-100 opacity-0 transition-all duration-300"
              />
            </div>
          </a>
        ))}
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
  return (
    <a
      className="relative rounded-lg p-6 group
      text-primary hover:bg-[var(--blue-2)] shadow-smAccent border bg-[var(--blue-1)]
      transition-all duration-300 cursor-pointer
      "
      href={`/?file=__new__`}
      target="_blank"
      rel="noreferrer"
    >
      <h2 className="text-lg font-semibold">Create a new notebook</h2>
      <div className="group-hover:opacity-100 opacity-0 absolute right-5 top-0 bottom-0 rounded-lg flex items-center justify-center transition-all duration-300">
        <FilePlus2Icon size={24} />
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
