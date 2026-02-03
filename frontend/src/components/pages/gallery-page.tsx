/* Copyright 2026 Marimo. All rights reserved. */

import { SearchIcon } from "lucide-react";
import type React from "react";
import { Suspense, useMemo, useState } from "react";
import { ErrorBoundary } from "@/components/editor/boundary/ErrorBoundary";
import { Spinner } from "@/components/icons/spinner";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { getSessionId } from "@/core/kernel/session";
import { useRequestClient } from "@/core/network/requests";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Banner } from "@/plugins/impl/common/error-banner";
import { prettyError } from "@/utils/errors";
import { PathBuilder, Paths } from "@/utils/paths";
import { asURL } from "@/utils/url";

const capitalize = (word: string): string => {
  return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
};

const titleCase = (path: string): string => {
  const delimiter = PathBuilder.guessDeliminator(path).deliminator;
  return path
    .replace(/\.[^./]+$/, "")
    .split(delimiter)
    .filter(Boolean)
    .map((part) => part.split(/[_-]/).map(capitalize).join(" "))
    .join(" > ");
};

const tabTarget = (path: string): string => {
  return `${getSessionId()}-${encodeURIComponent(path)}`;
};

const isHttpsUrl = (value: string): boolean => {
  try {
    const url = new URL(value);
    return url.protocol === "https:";
  } catch {
    return false;
  }
};

const SEARCH_THRESHOLD = 10;

const GalleryPage: React.FC = () => {
  const { getWorkspaceFiles } = useRequestClient();
  const [searchQuery, setSearchQuery] = useState("");
  const response = useAsyncData(
    () => getWorkspaceFiles({ includeMarkdown: false }),
    [],
  );
  const workspace = response.data;

  const formattedFiles = useMemo(() => {
    const files = workspace?.files ?? [];
    const root = workspace?.root ?? "";
    return files
      .filter((file) => !file.isDirectory)
      .map((file) => {
        const relativePath =
          root && Paths.isAbsolute(file.path) && file.path.startsWith(root)
            ? Paths.rest(file.path, root)
            : file.path;
        const title =
          file.opengraph?.title ?? titleCase(Paths.basename(relativePath));
        const subtitle = titleCase(Paths.dirname(relativePath));
        const description = file.opengraph?.description ?? "";
        const opengraphImage = file.opengraph?.image;
        const thumbnailUrl =
          opengraphImage && isHttpsUrl(opengraphImage)
            ? opengraphImage
            : asURL(
                `/api/home/thumbnail?file=${encodeURIComponent(relativePath)}`,
              ).toString();
        return {
          ...file,
          relativePath,
          title,
          subtitle,
          description,
          thumbnailUrl,
        };
      })
      .sort((a, b) => a.relativePath.localeCompare(b.relativePath));
  }, [workspace?.files, workspace?.root]);

  const filteredFiles = useMemo(() => {
    if (!searchQuery) {
      return formattedFiles;
    }
    const query = searchQuery.toLowerCase();
    return formattedFiles.filter((file) =>
      file.title.toLowerCase().includes(query),
    );
  }, [formattedFiles, searchQuery]);

  if (response.isPending) {
    return <Spinner centered={true} size="xlarge" className="mt-6" />;
  }

  if (response.error) {
    return (
      <Banner kind="danger" className="rounded p-4">
        {prettyError(response.error)}
      </Banner>
    );
  }

  if (!workspace) {
    return <Spinner centered={true} size="xlarge" className="mt-6" />;
  }

  return (
    <Suspense>
      <div className="flex flex-col gap-6 max-w-6xl container pt-5 pb-20 z-10">
        <img src="logo.png" alt="marimo logo" className="w-48 mb-2" />
        <ErrorBoundary>
          <div className="flex flex-col gap-2">
            {workspace.hasMore && (
              <Banner kind="warn" className="rounded p-4">
                Showing first {workspace.fileCount} files. Your workspace has
                more files.
              </Banner>
            )}
            {formattedFiles.length > SEARCH_THRESHOLD && (
              <Input
                id="search"
                value={searchQuery}
                icon={<SearchIcon className="h-4 w-4" />}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search"
                rootClassName="mb-3"
                className="mb-0 border-border"
              />
            )}
            {filteredFiles.length === 0 ? (
              <Banner kind="warn" className="rounded p-4">
                No marimo apps found.
              </Banner>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredFiles.map((file) => (
                  <a
                    key={file.path}
                    href={asURL(
                      `?file=${encodeURIComponent(file.relativePath)}`,
                    ).toString()}
                    target={tabTarget(file.path)}
                    className="no-underline"
                  >
                    <Card className="h-full overflow-hidden hover:bg-accent/20 transition-colors">
                      <img
                        src={file.thumbnailUrl}
                        alt={file.title}
                        loading="lazy"
                        className="w-full aspect-1200/630 object-cover border-b border-border/60"
                      />
                      <CardContent className="p-6 pt-4">
                        <div className="flex flex-col gap-1">
                          {file.subtitle && (
                            <div className="text-sm font-semibold text-muted-foreground">
                              {file.subtitle}
                            </div>
                          )}
                          <div className="text-lg font-medium">
                            {file.title}
                          </div>
                          {file.description && (
                            <div className="text-sm text-muted-foreground line-clamp-3 mt-1">
                              {file.description}
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </a>
                ))}
              </div>
            )}
          </div>
        </ErrorBoundary>
      </div>
    </Suspense>
  );
};

export default GalleryPage;
