/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { Spinner } from "@/components/icons/spinner";
import {
  isGitHubCopilotSignedInState,
  githubCopilotLoadingVersion,
} from "@/core/codemirror/copilot/state";
import { atom, useAtomValue } from "jotai";
import { userConfigAtom } from "@/core/config/config";
import { GitHubCopilotIcon } from "@/components/icons/github-copilot";

const copilotAtom = atom((get) => {
  return get(userConfigAtom).completion.copilot;
});

export const CopilotStatusIcon: React.FC = () => {
  const copilot = useAtomValue(copilotAtom);

  // We only show an icon for GitHub Copilot, but not for other copilot providers,
  // this can be extended in the future
  if (copilot === "github") {
    return <GitHubCopilotStatus />;
  }

  return null;
};

const GitHubCopilotStatus: React.FC = () => {
  const isGitHubCopilotSignedIn = useAtomValue(isGitHubCopilotSignedInState);
  const isLoading = useAtomValue(githubCopilotLoadingVersion) !== null;

  const label = isGitHubCopilotSignedIn ? "Ready" : "Not connected";

  return (
    <Tooltip content={`GitHub Copilot: ${label}`}>
      <span>
        {isLoading ? (
          <Spinner className="h-4 w-4" />
        ) : (
          <GitHubCopilotIcon
            className={cn("h-4 w-4", !isGitHubCopilotSignedIn && "opacity-60")}
          />
        )}
      </span>
    </Tooltip>
  );
};
