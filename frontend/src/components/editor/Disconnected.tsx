/* Copyright 2024 Marimo. All rights reserved. */
import { API } from "@/core/network/api";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";
import { prettyError } from "@/utils/errors";
import { reloadSafe } from "@/utils/reload-safe";
import { ArrowRightSquareIcon } from "lucide-react";
import { Banner } from "@/plugins/impl/common/error-banner";

interface DisconnectedProps {
  reason: string;
  canTakeover: boolean | undefined;
}

export const Disconnected = ({
  reason,
  canTakeover = false,
}: DisconnectedProps) => {
  const handleTakeover = async () => {
    try {
      const searchParams = new URL(window.location.href).searchParams;
      await API.post(`/kernel/takeover?${searchParams.toString()}`, {});

      // Refresh the page to reconnect
      reloadSafe();
    } catch (error) {
      toast({
        title: "Failed to take over session",
        description: prettyError(error),
        variant: "danger",
      });
    }
  };

  if (canTakeover) {
    // Show a banner instead
    return (
      <div className="flex justify-center">
        <Banner
          kind="info"
          className="mt-10 flex flex-col rounded p-3 max-w-[800px] mx-4"
        >
          <div className="flex justify-between">
            <span className="font-bold text-xl flex items-center mb-2">
              Notebook already connected
            </span>
          </div>
          <div className="flex justify-between items-end text-base gap-20">
            <span>{reason}</span>
            {canTakeover && (
              <Button
                onClick={handleTakeover}
                variant="outline"
                className="flex-shrink-0"
              >
                <ArrowRightSquareIcon className="w-4 h-4 mr-2" />
                Take over session
              </Button>
            )}
          </div>
        </Banner>
      </div>
    );
  }

  return (
    <div className="font-mono text-center text-base text-[var(--red-11)]">
      <p>{reason}</p>
    </div>
  );
};
