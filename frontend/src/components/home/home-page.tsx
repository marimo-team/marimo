/* Copyright 2024 Marimo. All rights reserved. */
import { getWorkspaceFiles, getRecentFiles } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import React, { Suspense } from "react";
import { Spinner } from "../icons/spinner";

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
      <div className="grid grid-cols-3 gap-4">
        <CreateNewNotebook />
        <ListedNotebooks files={data.workspace.files} />
        <RecentNotebooks files={data.recents.files} />
        <NotebookFromOrCodeUrl />
      </div>
    </Suspense>
  );
};

const ListedNotebooks: React.FC<{
  files: Array<{ name: string; path: string }>;
}> = ({ files }) => {
  return (
    <div>
      {files.map((file) => (
        <div key={file.path}>{file.name}</div>
      ))}
    </div>
  );
};

const RecentNotebooks: React.FC<{
  files: Array<{ name: string; path: string }>;
}> = ({ files }) => {
  return (
    <div>
      Recent Notebooks
      {files.map((file) => (
        <div key={file.path}>{file.name}</div>
      ))}
    </div>
  );
};

const CreateNewNotebook: React.FC = () => {
  return (
    <div className="bg-[var(--slate-2)] rounded-lg p-4 border border-[var(--slate-3)]">
      <h2 className="text-lg font-semibold">Create New Notebook</h2>
    </div>
  );
};

const NotebookFromOrCodeUrl: React.FC = () => {
  return (
    <div>
      Notebook From URL
      <input type="text" placeholder="Enter URL" />
    </div>
  );
};
