/* Copyright 2026 Marimo. All rights reserved. */

import { CaretDownIcon } from "@radix-ui/react-icons";
import {
  ActivityIcon,
  BarChart2Icon,
  BookMarkedIcon,
  BookOpenIcon,
  DatabaseIcon,
  FileIcon,
  FileTextIcon,
  GraduationCapIcon,
  GridIcon,
  LayoutIcon,
  MessagesSquareIcon,
  OrbitIcon,
  PackageIcon,
} from "lucide-react";
import type React from "react";
import { MarkdownIcon } from "@/components/editor/cell/code/icons";
import { GitHubIcon } from "@/components/icons/github";
import { YouTubeIcon } from "@/components/icons/youtube";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Constants } from "@/core/constants";
import { useRequestClient } from "@/core/network/requests";
import type { TutorialId } from "@/core/network/types";
import { Banner } from "@/plugins/impl/common/error-banner";
import { openNotebook } from "@/utils/links";
import { Objects } from "@/utils/objects";
import { MarimoPlusIcon } from "../icons/marimo-icons";

const TUTORIALS: Record<
  TutorialId,
  [string, React.FC<React.SVGProps<SVGSVGElement>>, string]
> = {
  intro: ["Introduction", BookOpenIcon, "Get started with marimo basics"],
  dataflow: [
    "Dataflow",
    ActivityIcon,
    "Learn how cells interact with each other",
  ],
  ui: ["UI Elements", LayoutIcon, "Create interactive UI components"],
  markdown: [
    "Markdown",
    FileTextIcon,
    "Format text with parameterized markdown",
  ],
  plots: ["Plots", BarChart2Icon, "Create interactive visualizations"],
  sql: ["SQL", DatabaseIcon, "Query databases directly in marimo"],
  layout: ["Layout", GridIcon, "Customize the layout of your cells' output"],
  fileformat: [
    "File format",
    FileIcon,
    "Understand marimo's pure-Python file format",
  ],
  "external-dependencies": [
    "External dependencies",
    PackageIcon,
    "Declare dependencies with Python script metadata",
  ],
  "for-jupyter-users": [
    "For Jupyter users",
    OrbitIcon,
    "Transiting from Jupyter to marimo",
  ],
  "markdown-format": [
    "Markdown format",
    MarkdownIcon,
    "Using marimo to edit markdown files",
  ],
};

export const OpenTutorialDropDown: React.FC = () => {
  const { openTutorial } = useRequestClient();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button
          data-testid="open-tutorial-button"
          size="sm"
          variant="outline"
          className="border-border text-(--gray-11) shadow-none hover:border-(--gray-7) hover:bg-(--gray-3)"
        >
          <GraduationCapIcon className="w-4 h-4 mr-2" />
          Tutorials
          <CaretDownIcon className="w-3 h-3 ml-1" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="end" className="print:hidden">
        {Objects.entries(TUTORIALS).map(
          ([tutorialId, [label, Icon, description]]) => (
            <DropdownMenuItem
              key={tutorialId}
              onSelect={async () => {
                const file = await openTutorial({ tutorialId });
                if (!file) {
                  return;
                }
                openNotebook(file.path);
              }}
            >
              <Icon
                strokeWidth={1.5}
                className="w-4 h-4 mr-3 self-start mt-1.5 text-muted-foreground"
              />
              <div className="flex items-center">
                <div className="flex flex-col">
                  <span>{label}</span>
                  <span className="text-xs text-muted-foreground pr-1">
                    {description}
                  </span>
                </div>
              </div>
            </DropdownMenuItem>
          ),
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const RESOURCES = [
  {
    title: "Documentation",
    description: "Official marimo documentation and API reference",
    icon: BookMarkedIcon,
    url: Constants.docsPage,
  },
  {
    title: "GitHub",
    description: "View source code, report issues, or contribute",
    icon: GitHubIcon,
    url: Constants.githubPage,
  },
  {
    title: "Discussion",
    description: "Join the marimo Discord community",
    icon: MessagesSquareIcon,
    url: Constants.discordLink,
  },
  {
    title: "molab",
    description: "Run marimo notebooks in the cloud",
    icon: MarimoPlusIcon,
    url: Constants.molab,
  },
  {
    title: "YouTube",
    description: "Watch tutorials and demos",
    icon: YouTubeIcon,
    url: Constants.youtube,
  },
  {
    title: "Changelog",
    description: "See what's new in marimo",
    icon: FileTextIcon,
    url: Constants.releasesPage,
  },
];

export const ResourceLinks: React.FC = () => {
  return (
    <nav
      aria-label="Resources"
      className="mt-12 border-t border-border/60 pt-6"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
        {RESOURCES.map((resource) => (
          <a
            key={resource.title}
            href={resource.url}
            target="_blank"
            rel="noreferrer"
            aria-label={`${resource.title}: ${resource.description}`}
            title={resource.description}
            className="flex items-center gap-2 rounded-sm text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
          >
            <resource.icon className="h-4 w-4" />
            <span>{resource.title}</span>
          </a>
        ))}
      </div>
    </nav>
  );
};

/**
 * Shown when the workspace scan stopped early, so the file list the user is
 * looking at is missing files and folders.
 */
export const TruncatedWorkspaceBanner: React.FC<{
  fileCount: number | undefined;
}> = ({ fileCount }) => {
  return (
    <Banner kind="warn" className="rounded p-4">
      Showing {fileCount} files. Some files and folders were skipped because
      your workspace is large or deeply nested. Start marimo from a subfolder to
      see them.
    </Banner>
  );
};
