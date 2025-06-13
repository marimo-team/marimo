/* Copyright 2024 Marimo. All rights reserved. */

import { CaretDownIcon } from "@radix-ui/react-icons";
import {
  ActivityIcon,
  BarChart2Icon,
  BookMarkedIcon,
  BookOpenIcon,
  DatabaseIcon,
  FileIcon,
  FileTextIcon,
  GithubIcon,
  GraduationCapIcon,
  GridIcon,
  LayoutIcon,
  LinkIcon,
  MessagesSquareIcon,
  OrbitIcon,
  YoutubeIcon,
} from "lucide-react";
import type React from "react";
import { MarkdownIcon } from "@/components/editor/cell/code/icons";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Constants } from "@/core/constants";
import { openTutorial } from "@/core/network/requests";
import type { TutorialId } from "@/core/network/types";
import { Objects } from "@/utils/objects";
import { asURL } from "@/utils/url";

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
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button data-testid="open-tutorial-button" size="xs" variant="outline">
          <GraduationCapIcon className="w-4 h-4 mr-2" />
          Tutorials
          <CaretDownIcon className="w-3 h-3 ml-1" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="bottom" align="end" className="no-print">
        {Objects.entries(TUTORIALS).map(
          ([tutorialId, [label, Icon, description]]) => (
            <DropdownMenuItem
              key={tutorialId}
              onSelect={async () => {
                const file = await openTutorial({ tutorialId });
                if (!file) {
                  return;
                }
                window.open(asURL(`?file=${file.path}`).toString(), "_blank");
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
    icon: GithubIcon,
    url: Constants.githubPage,
  },
  {
    title: "Community",
    description: "Join the marimo Discord community",
    icon: MessagesSquareIcon,
    url: Constants.discordLink,
  },
  {
    title: "YouTube",
    description: "Watch tutorials and demos",
    icon: YoutubeIcon,
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
    <div className="flex flex-col gap-2">
      <Header Icon={LinkIcon}>Resources</Header>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {RESOURCES.map((resource) => (
          <a
            key={resource.title}
            href={resource.url}
            target="_blank"
            className="flex items-start gap-3 py-3 px-3 rounded-lg border hover:bg-accent/20 transition-colors shadow-xs"
          >
            <resource.icon className="w-5 h-5 mt-1.5 text-primary" />
            <div>
              <h3 className="font-medium">{resource.title}</h3>
              <p className="text-sm text-muted-foreground">
                {resource.description}
              </p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
};

export const Header: React.FC<{
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  control?: React.ReactNode;
  children: React.ReactNode;
}> = ({ Icon, control, children }) => {
  return (
    <div className="flex items-center justify-between gap-2">
      <h2 className="flex items-center gap-2 text-xl font-semibold text-muted-foreground select-none">
        <Icon className="h-5 w-5" />
        {children}
      </h2>
      {control}
    </div>
  );
};
