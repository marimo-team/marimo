/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { cn } from "@/utils/cn";
import { Spinner } from "@/components/icons/spinner";
import {
  isGitHubCopilotSignedInState,
  githubCopilotLoadingVersion,
  copilotSignedInState,
} from "@/core/codemirror/copilot/state";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { resolvedMarimoConfigAtom } from "@/core/config/config";
import { GitHubCopilotIcon } from "@/components/icons/github-copilot";
import { FooterItem } from "../footer-item";
import { toast } from "@/components/ui/use-toast";
import { getCopilotClient } from "@/core/codemirror/copilot/client";
import { Logger } from "@/utils/Logger";
import { Button } from "@/components/ui/button";
import { useOnMount } from "@/hooks/useLifecycle";
import { useOpenSettingsToTab } from "@/components/app-config/state";

const copilotAtom = atom((get) => {
  return get(resolvedMarimoConfigAtom).completion.copilot;
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

const logger = Logger.get("[copilot-status-bar]");

const GitHubCopilotStatus: React.FC = () => {
  const isGitHubCopilotSignedIn = useAtomValue(isGitHubCopilotSignedInState);
  const isLoading = useAtomValue(githubCopilotLoadingVersion) !== null;
  const { handleClick } = useOpenSettingsToTab();
  const openSettings = () => handleClick("ai");

  const label = isGitHubCopilotSignedIn ? "Ready" : "Not connected";
  const setCopilotSignedIn = useSetAtom(isGitHubCopilotSignedInState);
  const setStep = useSetAtom(copilotSignedInState);

  // Check connection on mount
  useOnMount(() => {
    const client = getCopilotClient();
    let mounted = true;

    const checkConnection = async () => {
      try {
        // If we fail to initialize, show connection error
        await client.initializePromise.catch((error) => {
          logger.error("Failed to initialize", error);
          client.close();
          throw error;
        });

        if (!mounted) {
          return;
        }

        const signedIn = await client.signedIn();
        if (!mounted) {
          return;
        }

        setCopilotSignedIn(signedIn);
        setStep(signedIn ? "signedIn" : "signedOut");
      } catch (error) {
        if (!mounted) {
          return;
        }
        logger.warn("Connection failed", error);
        setCopilotSignedIn(false);
        setStep("connectionError");
        toast({
          title: "GitHub Copilot Connection Error",
          description:
            "Failed to connect to GitHub Copilot. Check settings and try again.",
          variant: "danger",
          action: (
            <Button variant="link" onClick={openSettings}>
              Settings
            </Button>
          ),
        });
      }
    };

    checkConnection();

    return () => {
      mounted = false;
    };
  });

  return (
    <FooterItem
      tooltip={
        <>
          <b>GitHub Copilot:</b> {label}
        </>
      }
      selected={false}
      onClick={openSettings}
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
