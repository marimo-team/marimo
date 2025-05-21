/* Copyright 2024 Marimo. All rights reserved. */
import { useAtom } from "jotai";
import { copilotSignedInState, isGitHubCopilotSignedInState } from "./state";
import { memo, useState } from "react";
import { getCopilotClient } from "./client";
import { Button, buttonVariants } from "@/components/ui/button";
import { CheckIcon, CopyIcon, Loader2Icon, XIcon } from "lucide-react";
import { ExternalLink } from "@/components/ui/links";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/use-toast";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import type { GitHubCopilotStatus } from "./types";

export const CopilotConfig = memo(() => {
  const [copilotSignedIn, copilotChangeSignIn] = useAtom(
    isGitHubCopilotSignedInState,
  );
  const [step, setStep] = useAtom(copilotSignedInState);
  const [localData, setLocalData] = useState<{ url: string; code: string }>();
  const [loading, setLoading] = useState(false);

  const trySignIn = async (evt: React.MouseEvent) => {
    evt.preventDefault();
    setLoading(true);
    try {
      const { verificationUri, status, userCode } = await initiateSignIn();
      if (isSignedIn(status)) {
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

    setLoading(true);
    try {
      const result = await handleSignInConfirmation(localData.code);
      if (result.success) {
        copilotChangeSignIn(true);
        setStep("signedIn");
      } else if (result.error === "connection") {
        setStep("connectionError");
        toast({
          title: "GitHub Copilot Connection Error",
          description: "Lost connection during sign-in. Please try again.",
          variant: "danger",
          action: <Button onClick={trySignIn}>Retry</Button>,
        });
      } else {
        setStep("signInFailed");
      }
    } finally {
      setLoading(false);
    }
  };

  const signOut = async (evt: React.MouseEvent) => {
    evt.preventDefault();
    await handleSignOut();
    copilotChangeSignIn(false);
    setStep("signedOut");
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
              <ExternalLink href="https://docs.marimo.io/getting_started/index.html#github-copilot">
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

// Utility functions
const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 3000;

async function initiateSignIn() {
  const client = getCopilotClient();
  return await client.signInInitiate();
}

async function handleSignInConfirmation(userCode: string) {
  const client = getCopilotClient();

  try {
    Logger.log("Copilot#tryFinishSignIn: Attempting to confirm sign-in");
    const { status } = await client.signInConfirm({ userCode });

    if (isSignedIn(status)) {
      Logger.log("Copilot#tryFinishSignIn: Sign-in confirmed successfully");
      return { success: true };
    }

    Logger.warn(
      "Copilot#tryFinishSignIn: Sign-in confirmation returned unexpected status",
      { status },
    );
    return { success: false };
  } catch (error) {
    if (isConnectionError(error)) {
      Logger.error(
        "Copilot#tryFinishSignIn: Connection error during sign-in",
        error,
      );
      return { success: false, error: "connection" };
    }

    return await handleSignInRetry(client);
  }
}

async function handleSignInRetry(client: ReturnType<typeof getCopilotClient>) {
  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
      const signedIn = await client.signedIn();
      if (signedIn) {
        Logger.log(
          "Copilot#tryFinishSignIn: Successfully signed in after retry",
        );
        return { success: true };
      }
    } catch (retryError) {
      Logger.warn("Copilot#tryFinishSignIn: Retry attempt failed", {
        attempt: i + 1,
        maxRetries: MAX_RETRIES,
      });

      if (isConnectionError(retryError)) {
        return { success: false, error: "connection" };
      }
    }
  }

  Logger.error("Copilot#tryFinishSignIn: All sign-in attempts failed");
  return { success: false };
}

async function handleSignOut() {
  const client = getCopilotClient();
  await client.signOut();
}

function isConnectionError(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.message.includes("ECONNREFUSED") ||
      error.message.includes("WebSocket") ||
      error.message.includes("network"))
  );
}

function isSignedIn(status: GitHubCopilotStatus): boolean {
  return (
    status === "SignedIn" || status === "AlreadySignedIn" || status === "OK"
  );
}
