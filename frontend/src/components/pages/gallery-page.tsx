/* Copyright 2024 Marimo. All rights reserved. */
import { getWorkspaceFiles } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import type React from "react";
import { Suspense, useState, useMemo } from "react";
import { Spinner } from "../icons/spinner";
import { Search } from "lucide-react";
import { Card, CardContent } from "../ui/card";
import { asURL } from "@/utils/url";
import { ErrorBoundary } from "../editor/boundary/ErrorBoundary";
import { Banner } from "@/plugins/impl/common/error-banner";
import { prettyError } from "@/utils/errors";
import { getSessionId } from "@/core/kernel/session";
import { Input } from "../ui/input";
import { PathBuilder, Paths } from "@/utils/paths";

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function titleCase(str: string): string {
  const deliminator = PathBuilder.guessDeliminator(str).deliminator;
  return str
    .replace(/\.[^./]+$/, "") // Remove file extension
    .split(deliminator) // Split by forward or backslash
    .filter(Boolean)
    .map((part) => part.split(/[_-]/).map(capitalize).join(" ")) // Capitalize each word
    .join(" > ");
}

function tabTarget(path: string) {
  // Consistent tab target so we open in the same tab when clicking on the same notebook
  return `${getSessionId()}-${encodeURIComponent(path)}`;
}

const SEARCH_THRESHOLD = 10;

const GalleryPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const workspaceResponse = useAsyncData(async () => {
    const files = await getWorkspaceFiles({ includeMarkdown: false });
    return (
      files.files
        // Add title
        .map((file) => {
          const relativePath = file.path.replace(files.root, "");
          return {
            ...file,
            // path: relativePath,
            subtitle: titleCase(Paths.dirname(relativePath)),
            title: titleCase(Paths.basename(file.path)),
          };
        })
        // Sort by relative path
        .sort((a, b) => a.path.localeCompare(b.path))
    );
  }, []);

  const filteredFiles = useMemo(() => {
    if (!workspaceResponse.data) {
      return [];
    }
    const files = workspaceResponse.data;
    if (!searchQuery) {
      return files;
    }
    return files.filter((file) =>
      file.title.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [workspaceResponse.data, searchQuery]);

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

  const files = workspaceResponse.data;

  return (
    <Suspense>
      <div className="flex flex-col gap-6 max-w-6xl container pt-5 pb-20 z-10">
        <img src="logo.png" alt="marimo logo" className="w-48 mb-2" />
        <ErrorBoundary>
          <div className="flex flex-col gap-2">
            {files.length > SEARCH_THRESHOLD && (
              <div className="relative mb-6">
                <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-muted-foreground h-5 w-5" />
                <Input
                  placeholder="Search…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-12 h-12 text-lg border-border bg-muted/20 mb-0"
                />
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredFiles.map((file) => (
                <a
                  key={file.path}
                  href={asURL(`?file=${file.path}`).toString()}
                  target={tabTarget(file.path)}
                  className="no-underline"
                >
                  <Card className="h-full hover:bg-accent/20 transition-colors">
                    <CardContent className="p-6">
                      <div className="flex flex-col gap-1">
                        {file.subtitle && (
                          <div className="text-sm font-semibold text-muted-foreground">
                            {file.subtitle}
                          </div>
                        )}
                        <div className="text-lg font-medium">{file.title}</div>
                      </div>
                    </CardContent>
                  </Card>
                </a>
              ))}
            </div>
          </div>
        </ErrorBoundary>
      </div>
    </Suspense>
  );
};

export default GalleryPage;
