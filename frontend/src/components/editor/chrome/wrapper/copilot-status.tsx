/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { cn } from "@/utils/cn";
import { Spinner } from "@/components/icons/spinner";
import {
  isGitHubCopilotSignedInState,
  githubCopilotLoadingVersion,
} from "@/core/codemirror/copilot/state";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { aiEnabledAtom, userConfigAtom } from "@/core/config/config";
import { GitHubCopilotIcon } from "@/components/icons/github-copilot";
import { SparklesIcon } from "lucide-react";
import { FooterItem } from "./footer-item";
import { activeUserConfigCategoryAtom } from "@/components/app-config/user-config-form";
import { settingDialogAtom } from "@/components/app-config/app-config-button";

export const AIStatusIcon: React.FC = () => {
  const ai = useAtomValue(aiAtom);
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const model = ai?.open_ai?.model || "gpt-4-turbo";
  const { handleClick } = useOpenAISettings();

  if (!aiEnabled) {
    return (
      <FooterItem
        tooltip="Assist is disabled"
        selected={false}
        onClick={handleClick}
      >
        <SparklesIcon className="h-4 w-4 opacity-60" />
      </FooterItem>
    );
  }

  return (
    <FooterItem
      tooltip={
        <>
          <b>Assist model:</b> {model}
        </>
      }
      onClick={handleClick}
      selected={false}
    >
      <SparklesIcon className="h-4 w-4" />
    </FooterItem>
  );
};

const copilotAtom = atom((get) => {
  return get(userConfigAtom).completion.copilot;
});
const aiAtom = atom((get) => {
  return get(userConfigAtom).ai;
});

export function useOpenAISettings() {
  const setActiveCategory = useSetAtom(activeUserConfigCategoryAtom);
  const setSettingsDialog = useSetAtom(settingDialogAtom);
  const handleClick = () => {
    setActiveCategory("ai");
    setSettingsDialog(true);
  };
  return { handleClick };
}

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
  const { handleClick } = useOpenAISettings();

  const label = isGitHubCopilotSignedIn ? "Ready" : "Not connected";

  return (
    <FooterItem
      tooltip={
        <>
          <b>GitHub Copilot:</b> {label}
        </>
      }
      selected={false}
      onClick={handleClick}
    >
      <span>
        {isLoading ? (
          <Spinner className="h-4 w-4" />
        ) : (
          <GitHubCopilotIcon
            className={cn("h-4 w-4", !isGitHubCopilotSignedIn && "opacity-60")}
          />
        )}
      </span>
    </FooterItem>
  );
};
