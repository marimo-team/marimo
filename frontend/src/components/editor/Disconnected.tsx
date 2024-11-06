/* Copyright 2024 Marimo. All rights reserved. */
import { API } from "@/core/network/api";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";
import { prettyError } from "@/utils/errors";
import { reloadSafe } from "@/utils/reload-safe";

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

  return (
    <div id="Disconnected">
      <p>{reason}</p>
      {canTakeover && (
        <Button onClick={handleTakeover} variant="secondary" className="mt-2">
          Take over session
        </Button>
      )}
    </div>
  );
};
