/* Copyright 2023 Marimo. All rights reserved. */
import { useAtom } from "jotai";
import { copilotSignedInState } from "./state";
import { memo, useEffect, useState } from "react";
import { getCopilotClient } from "./client";
import { Button, buttonVariants } from "@/components/ui/button";
import { CheckIcon, CopyIcon, Loader2Icon, XIcon } from "lucide-react";
import { Label } from "@/components/ui/label";
import { toast } from "@/components/ui/use-toast";

type Step =
  | "signedIn"
  | "signingIn"
  | "signInFailed"
  | "signedOut"
  | "connecting"
  | "notConnected";

export const CopilotConfig = memo(() => {
  const [copilotSignedIn, copilotChangeSignIn] = useAtom(copilotSignedInState);
  const [step, setStep] = useState<Step>();

  const [localData, setLocalData] = useState<{ url: string; code: string }>();
  const [loading, setLoading] = useState(false);

  // Check connection on mount
  useEffect(() => {
    const client = getCopilotClient();
    // If we fail to initialize, show not connected
    client.initializePromise.catch(() => {
      copilotChangeSignIn(false);
      setStep("notConnected");
    });
    client
      .signedIn()
      .then((signedIn) => {
        copilotChangeSignIn(signedIn);
        setStep(signedIn ? "signedIn" : "signedOut");
      })
      .catch(() => {
        copilotChangeSignIn(false);
        setStep("notConnected");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    try {
      setLoading(true);
      const { status } = await client.signInConfirm({
        userCode: localData.code,
      });

      if (status === "OK" || status === "AlreadySignedIn") {
        copilotChangeSignIn(true);
        setStep("signedIn");
      } else {
        setStep("signInFailed");
      }
    } catch {
      // If request failed, try seeing if we're already signed in
      // otherwise, show the error
      // We try 3 times, waiting 1 second between each try
      for (let i = 0; i < 3; i++) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        const signedIn = await client.signedIn();
        if (signedIn) {
          copilotChangeSignIn(true);
          setStep("signedIn");
          return;
        }
      }
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
                  onClick={() => {
                    if (!localData) {
                      return;
                    }
                    navigator.clipboard.writeText(localData.code);
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
          <div className="flex items-center justify-between">
            <Label className="font-normal flex">
              <CheckIcon className="h-4 w-4 mr-1" />
              Connected
            </Label>
            <Button onClick={signOut} size="xs" variant="text">
              Disconnect
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
              <a
                className="hyperlink"
                href="https://docs.marimo.io/getting_started/index.html#github-copilot"
                target="_blank"
                rel="noreferrer"
              >
                docs
              </a>
              .
            </div>
          </div>
        );
    }
  };

  return renderBody();
});
CopilotConfig.displayName = "CopilotConfig";
