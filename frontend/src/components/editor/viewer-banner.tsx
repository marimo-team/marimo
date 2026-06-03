/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai/react";
import { ArrowRightSquareIcon, EyeIcon } from "lucide-react";
import { kioskModeAtom } from "@/core/mode";
import { API } from "@/core/network/api";
import { Banner } from "@/plugins/impl/common/error-banner";
import { prettyError } from "@/utils/errors";
import { Button } from "../ui/button";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";

export const ViewerBanner = () => {
  const isViewing = useAtomValue(kioskModeAtom);

  if (!isViewing) {
    return null;
  }

  const handleTakeover = async () => {
    try {
      const searchParams = new URL(window.location.href).searchParams;
      // No reload: the server replies with consumer-capabilities
      // (edit: true), which flips kiosk mode off and hides this banner.
      await API.post(`/kernel/takeover?${searchParams.toString()}`, {});
    } catch (error) {
      toast({
        title: "Failed to take over session",
        description: prettyError(error),
        variant: "danger",
      });
    }
  };

  return (
    <div className="fixed top-2 left-14 z-50 w-fit print:hidden">
      <Banner
        kind="info"
        className="flex items-center gap-2 rounded px-2 py-1 text-xs shadow-sm"
      >
        <span className="flex items-center gap-1 text-muted-foreground">
          <EyeIcon className="w-3.5 h-3.5 shrink-0" />
          You are currently connected as a reader.
        </span>
        <Tooltip
          content="Switch editing to this tab. The current editor becomes read-only."
          side="bottom"
        >
          <Button
            onClick={handleTakeover}
            variant="outline"
            size="xs"
            data-testid="takeover-button"
            className="shrink-0"
          >
            <ArrowRightSquareIcon className="w-3 h-3 mr-1" />
            Take over
          </Button>
        </Tooltip>
      </Banner>
    </div>
  );
};
