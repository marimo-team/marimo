/* Copyright 2023 Marimo. All rights reserved. */
import { useAtom } from "jotai";
import { copilotState } from "./state";
import { memo, useEffect, useState } from "react";
import { getCopilotClient } from "./client";
import { Button, buttonVariants } from "@/components/ui/button";
import { CopyIcon, Loader2Icon } from "lucide-react";
import { FormItem } from "@/components/ui/form";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { toast } from "@/components/ui/use-toast";

export const CopilotConfig = memo(() => {
  const [state, dispatch] = useAtom(copilotState);
  const { copilotSignedIn, copilotEnabled } = state;
  const client = getCopilotClient();

  const copilotChangeSignIn = (signedIn: boolean) =>
    dispatch({ type: "signedIn", signedIn: signedIn });
  const enableCopilot = (enabled: boolean) =>
    dispatch({ type: "copilotEnabled", enabled: enabled });

  const [step, setStep] = useState<
    "signedIn" | "signingIn" | "signInFailed" | "signedOut"
  >(copilotSignedIn ? "signedIn" : "signedOut");

  const [localData, setLocalData] = useState<{ url: string; code: string }>();
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // If null, we haven't checked yet
    if (copilotSignedIn == null) {
      client.signedIn().then((signedIn) => {
        copilotChangeSignIn(signedIn);
      });
    } else {
      setStep(copilotSignedIn ? "signedIn" : "signedOut");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [copilotSignedIn]);

  const trySignIn = async () => {
    setLoading(true);
    try {
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

  const tryFinishSignIn = async () => {
    if (!localData) {
      return;
    }
    try {
      setLoading(true);
      const { status } = await client.signInConfirm({
        userCode: localData.code,
      });

      if (status === "OK" || status === "AlreadySignedIn") {
        copilotChangeSignIn(true);
      } else {
        setStep("signInFailed");
      }
    } catch {
      // If request failed, try seeing if we're already signed in
      // otherwise, show the error
      const signedIn = await client.signedIn();
      if (signedIn) {
        copilotChangeSignIn(true);
      } else {
        setStep("signInFailed");
      }
    } finally {
      setLoading(false);
    }
  };

  const signOut = async () => {
    const client = getCopilotClient();
    await client.signOut();
    copilotChangeSignIn(false);
  };

  const renderBody = () => {
    switch (step) {
      case "signedOut":
        return (
          <Button onClick={trySignIn} size="xs">
            Connect to GitHub Copilot
          </Button>
        );

      case "signingIn":
        return (
          <ol className="ml-4 text-sm list-decimal [&>li]:mt-2">
            <li>
              Please click this link:
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
              <div className="flex items-center">
                Enter this code:
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
              <Button onClick={trySignIn} size="xs">
                Connect to GitHub Copilot
              </Button>
            )}
          </div>
        );

      case "signedIn":
        return (
          <div className="flex items-center justify-between">
            <FormItem className="flex flex-row items-center space-x-2 space-y-0">
              <Switch
                checked={copilotEnabled}
                size="sm"
                onCheckedChange={(checked) => enableCopilot(checked)}
              />
              <Label className="font-normal">Enable</Label>
            </FormItem>
            <Button onClick={signOut} size="xs" variant="ghost">
              Disconnect
            </Button>
          </div>
        );
    }
  };

  if (step === "signedOut") {
    return renderBody();
  }

  return (
    <div className="flex flex-col space-y-2">
      <Label className="font-normal">GitHub Copilot</Label>
      {renderBody()}
    </div>
  );
});
CopilotConfig.displayName = "CopilotConfig";
