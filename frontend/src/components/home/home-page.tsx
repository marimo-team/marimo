/* Copyright 2024 Marimo. All rights reserved. */
import { getWorkspaceFiles, getRecentFiles } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import React, { Suspense } from "react";
import { cn } from "@/utils/cn";
import { Spinner } from "../icons/spinner";
import { ArrowRightIcon } from "lucide-react";
import { Input } from "../ui/input";

import "./grid-background.css";

export const HomePage: React.FC = () => {
  const { data, loading, error } = useAsyncData(async () => {
    const [workspace, recents] = await Promise.all([
      getWorkspaceFiles(),
      getRecentFiles(),
    ]);
    return { workspace, recents };
  }, []);

  if (error) {
    throw error;
  }

  if (loading || !data) {
    return <Spinner centered={true} size="xlarge" />;
  }

  return (
    <Suspense>
      <GridBackground />
      <div className="flex flex-col gap-8 max-w-5xl container pt-10 pb-20 z-10">
        <img src="/logo.png" alt="Marimo Logo" className="w-64 mb-10" />
        <CreateNewNotebook />
        <NotebookList header="Recent Notebooks" files={data.recents.files} />
        <NotebookList header="Workspace" files={data.workspace.files} />
        {/* <NotebookFromOrCodeUrl /> */}
      </div>
    </Suspense>
  );
};

const NotebookList: React.FC<{
  header: string;
  files: Array<{ name: string; path: string }>;
}> = ({ header, files }) => {
  if (files.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-4">
      <Header>{header}</Header>
      <div
        className="flex flex-col divide-y divide-[var(--slate-3)] border rounded overflow-hidden
        max-h-96 overflow-y-auto shadow-sm bg-background
      "
      >
        {files.map((file) => (
          <a
            className="py-2 px-4 hover:bg-[var(--slate-3)] cursor-pointer transition-all duration-300 cursor-pointer group relative"
            key={file.path}
            href={`/?file=${file.path}`}
            target="_blank"
            rel="noreferrer"
          >
            <div className="flex flex-col justify-between">
              <h3 className="text-lg font-semibold">{file.name}</h3>
              <p
                title={file.path}
                className="text-sm text-muted-foreground
                overflow-hidden whitespace-nowrap overflow-ellipsis
              "
              >
                {file.path}
              </p>
            </div>
            <div className="group-hover:opacity-100 opacity-0 absolute right-5 top-0 bottom-0 rounded-lg flex items-center justify-center transition-all duration-300 text-muted-foreground">
              <ArrowRightIcon size={24} />
            </div>
          </a>
        ))}
      </div>
    </div>
  );
};

const Header: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <h2 className="text-2xl font-semibold">{children}</h2>;
};

const CreateNewNotebook: React.FC = () => {
  return (
    <a
      className="
      relative
      rounded-lg p-6 border
      shadow-sm hover:shadow-md transition-all duration-300 cursor-pointer
      text-[var(--grass-9)]
      bg-[var(--grass-1)] hover:bg-[var(--grass-2)]
      border-[var(--grass-7)] hover:border-[var(--grass-8)]
      group
    "
      href={`/?file=__new__`}
      target="_blank"
      rel="noreferrer"
    >
      <h2 className="text-lg font-semibold">Create new notebook</h2>
      <div className="group-hover:opacity-100 opacity-0 absolute right-5 top-0 bottom-0 rounded-lg flex items-center justify-center transition-all duration-300">
        <ArrowRightIcon size={24} />
      </div>
    </a>
  );
};

const NotebookFromOrCodeUrl: React.FC = () => {
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-lg font-semibold">
        Open a notebook from URL or paste code
      </h3>
      <Input
        className="h-12 px-4 border-border"
        type="text"
        placeholder="Enter URL"
      />
    </div>
  );
};

const GridBackground = (props: { className?: string }) => {
  return (
    <div
      className={cn(
        "bg-grid absolute inset-0 -z-10 [mask-image:linear-gradient(180deg,black,transparent)]",
        props.className,
      )}
    />
  );
};
