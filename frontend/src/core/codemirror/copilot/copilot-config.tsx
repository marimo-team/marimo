/* Copyright 2024 Marimo. All rights reserved. */
import { useAtom } from "jotai";
import { copilotSignedInState, isGitHubCopilotSignedInState } from "./state";
import { memo, useState } from "react";
import { getCopilotClient } from "./client";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  CheckIcon,
  CopyIcon,
  ExternalLink,
  Loader2Icon,
  XIcon,
} from "lucide-react";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import { useOpenSettingsToTab } from "@/components/app-config/state";

export const CopilotConfig = memo(() => {
  const [copilotSignedIn, copilotChangeSignIn] = useAtom(
    isGitHubCopilotSignedInState,
  );
  const [step, setStep] = useAtom(copilotSignedInState);
  const { handleClick: openSettings } = useOpenSettingsToTab();
  const [localData, setLocalData] = useState<{ url: string; code: string }>();
  const [loading, setLoading] = useState(false);

  const trySignIn = async (evt: React.MouseEvent) => {
    evt.preventDefault();
    setLoading(true);
    try {
      const client = getCopilotClient();
      const { verificationUri, status, userCode } =
        await client.signInInitiate();

      if (status === "OK" || status === "AlreadySignedIn") {
        copilotChangeSignIn(true);
      } else {
        setStep("signingIn");
        setLocalData({ url: verificationUri, code: userCode });
      }
    } finally {
      setLoading(false);
    }
  };

  const tryFinishSignIn = async (evt: React.MouseEvent) => {
    evt.preventDefault();
    if (!localData) {
      return;
    }
    const client = getCopilotClient();
    const MAX_RETRIES = 3;
    const RETRY_DELAY_MS = 1000;

    try {
      setLoading(true);
      Logger.log("Copilot#tryFinishSignIn: Attempting to confirm sign-in");
      const { status } = await client.signInConfirm({
        userCode: localData.code,
      });

      if (status === "OK" || status === "AlreadySignedIn") {
        Logger.log("Copilot#tryFinishSignIn: Sign-in confirmed successfully");
        copilotChangeSignIn(true);
        setStep("signedIn");
      } else {
        Logger.warn(
          "Copilot#tryFinishSignIn: Sign-in confirmation returned unexpected status",
          { status },
        );
        setStep("signInFailed");
      }
    } catch (error) {
      Logger.warn(
        "Copilot#tryFinishSignIn: Initial sign-in confirmation failed, attempting retries",
      );

      // Check if it's a connection error
      if (
        error instanceof Error &&
        (error.message.includes("ECONNREFUSED") ||
          error.message.includes("WebSocket") ||
          error.message.includes("network"))
      ) {
        Logger.error(
          "Copilot#tryFinishSignIn: Connection error during sign-in",
          error,
        );
        setStep("connectionError");
        toast({
          title: "GitHub Copilot Connection Error",
          description: "Lost connection during sign-in. Please try again.",
          variant: "danger",
          action: <Button onClick={trySignIn}>Retry</Button>,
        });
        return;
      }

      // If not a connection error, try seeing if we're already signed in
      // We try multiple times with a delay between attempts
      for (let i = 0; i < MAX_RETRIES; i++) {
        try {
          await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
          const signedIn = await client.signedIn();
          if (signedIn) {
            Logger.log(
              "Copilot#tryFinishSignIn: Successfully signed in after retry",
            );
            copilotChangeSignIn(true);
            setStep("signedIn");
            return;
          }
        } catch (retryError) {
          Logger.warn("Copilot#tryFinishSignIn: Retry attempt failed", {
            attempt: i + 1,
            maxRetries: MAX_RETRIES,
          });
          // Check for connection errors during retry
          if (
            retryError instanceof Error &&
            (retryError.message.includes("ECONNREFUSED") ||
              retryError.message.includes("WebSocket") ||
              retryError.message.includes("network"))
          ) {
            setStep("connectionError");
            toast({
              title: "GitHub Copilot Connection Error",
              description:
                "Lost connection during sign-in. Please check settings and try again.",
              variant: "danger",
              action: (
                <Button variant="link" onClick={() => openSettings("ai")}>
                  Settings
                </Button>
              ),
            });
            return;
          }
        }
      }
      Logger.error("Copilot#tryFinishSignIn: All sign-in attempts failed");
      setStep("signInFailed");
    } finally {
      setLoading(false);
    }
  };

  const signOut = async (evt: React.MouseEvent) => {
    evt.preventDefault();
    const client = getCopilotClient();
    copilotChangeSignIn(false);
    setStep("signedOut");
    await client.signOut();
  };

  const renderBody = () => {
    // If we don't have a step set, infer it from the current state
    const resolvedStep = step ?? (copilotSignedIn ? "signedIn" : "connecting");

    switch (resolvedStep) {
      case "connecting":
        return <Label className="font-normal flex">Connecting...</Label>;
      case "signedOut":
        return (
          <Button onClick={trySignIn} size="xs" variant="link">
            Sign in to GitHub Copilot
          </Button>
        );

      case "signingIn":
        return (
          <ol className="ml-4 text-sm list-decimal [&>li]:mt-2">
            <li>
              <div className="flex items-center">
                Copy this code:
                <strong className="ml-2">{localData?.code}</strong>
                <CopyIcon
                  className="ml-2 cursor-pointer opacity-60 hover:opacity-100 h-3 w-3"
                  onClick={async () => {
                    if (!localData) {
                      return;
                    }
                    await copyToClipboard(localData.code);
                    toast({
                      description: "Copied to clipboard",
                    });
                  }}
                />
              </div>
            </li>
            <li>
              Enter the code at this link:
              <a
                href={localData?.url}
                target="_blank"
                rel="noreferrer"
                className={buttonVariants({ variant: "link", size: "xs" })}
              >
                {localData?.url}
              </a>
            </li>
            <li>
              Click here when done:
              <Button size="xs" onClick={tryFinishSignIn} className="ml-1">
                {loading && (
                  <Loader2Icon className="h-3 w-3 mr-1 animate-spin" />
                )}
                Done
              </Button>
            </li>
          </ol>
        );

      case "signInFailed":
        return (
          <div className="flex flex-col gap-1">
            <div className="text-destructive text-sm">
              Sign in failed. Please try again.
            </div>
            {loading ? (
              <Loader2Icon className="h-3 w-3 mr-1 animate-spin" />
            ) : (
              <Button onClick={trySignIn} size="xs" variant="link">
                Connect to GitHub Copilot
              </Button>
            )}
          </div>
        );

      case "signedIn":
        return (
          <div className="flex items-center gap-5">
            <Label className="font-normal flex items-center">
              <div className="inline-flex items-center justify-center bg-[var(--grass-7)] rounded-full p-1 mr-2">
                <CheckIcon className="h-3 w-3 text-white" />
              </div>
              Connected
            </Label>
            <Button onClick={signOut} size="xs" variant="text">
              Disconnect
            </Button>
          </div>
        );

      case "connectionError":
        return (
          <div className="flex flex-col gap-1">
            <Label className="font-normal flex">
              <XIcon className="h-4 w-4 mr-1" />
              Connection Error
            </Label>
            <div className="text-sm">Unable to connect to GitHub Copilot.</div>
            <Button onClick={trySignIn} size="xs" variant="link">
              Retry Connection
            </Button>
          </div>
        );

      case "notConnected":
        return (
          <div className="flex flex-col gap-1">
            <Label className="font-normal flex">
              <XIcon className="h-4 w-4 mr-1" />
              Unable to connect
            </Label>
            <div className="text-sm">
              For troubleshooting, see the{" "}
              <ExternalLink
                href="https://docs.marimo.io/getting_started/index.html#github-copilot"
                target="_blank"
              >
                docs
              </ExternalLink>
              .
            </div>
          </div>
        );
    }
  };

  return renderBody();
});
CopilotConfig.displayName = "CopilotConfig";
