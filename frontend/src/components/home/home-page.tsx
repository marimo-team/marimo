/* Copyright 2024 Marimo. All rights reserved. */
import { getWorkspaceFiles, getRecentFiles } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import React, { Suspense } from "react";
import { cn } from "@/utils/cn";
import { Spinner } from "../icons/spinner";
import { FilePlus2Icon, ExternalLinkIcon } from "lucide-react";

// import "./grid-background.css";

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
      {/*<GridBackground />*/}
      <div className="flex flex-col gap-8 max-w-5xl container pt-10 pb-20 z-10">
          {/* TODO: Power off server button in top right */ }
          <img src="/logo.png" alt="Marimo Logo" className="w-64 mb-10" />
        <CreateNewNotebook />
        {/* TODO: section for running notebooks, option to turn them off */}
        <NotebookList header="Recent notebooks" files={data.recents.files} />
        <NotebookList header="All notebooks" files={data.workspace.files} />
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
        max-h-[48rem] overflow-y-auto shadow-sm bg-background
      "
      >
        {files.map((file) => (
          <a
            className="py-2 px-4 hover:bg-[var(--blue-2)] hover:text-primary transition-all duration-300 cursor-pointer group relative"
            key={file.path}
            href={`/?file=${file.path}`}
            target="_blank"
            rel="noreferrer"
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
            <div className="group-hover:opacity-100 opacity-0 absolute right-5 top-0 bottom-0 rounded-lg flex items-center justify-center transition-all duration-300 text-muted-foreground">
              {/* TODO: different icon/action depending on whether notebook is running */}
              <ExternalLinkIcon className="text-primary" size={24} />
            </div>
          </a>
        ))}
      </div>
    </div>
  );
};

const Header: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return <h2 className="text-xl font-semibold text-muted-foreground">{children}</h2>;
};

const CreateNewNotebook: React.FC = () => {
  return (
    <a
      className="relative rounded-lg p-6 group
      text-primary hover:bg-[var(--blue-2)] shadow-smAccent border
      transition-all duration-300 cursor-pointer
      "
      href={`/?file=__new__`}
      target="_blank"
      rel="noreferrer"
    >
      <h2 className="text-lg font-semibold">Create new notebook</h2>
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

const GridBackground = (props: { className?: string }) => {
  return (
    <div
      className={cn(
        "bg-grid absolute inset-0 -z-10 [mask-image:linear-gradient(180deg,black,transparent)]",
        props.className
      )}
    />
  );
};
