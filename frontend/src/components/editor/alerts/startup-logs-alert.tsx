/* Copyright 2024 Marimo. All rights reserved. */
import { BoxIcon, XIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { useEvent } from "react-use-event-hook";
import { useAlertActions, useAlerts } from "@/core/alerts/state";
import { Banner } from "@/plugins/impl/common/error-banner";
import { Button } from "../../ui/button";

export const StartupLogsAlert: React.FC = () => {
  const { startupLogsAlert } = useAlerts();
  const { clearStartupLogsAlert } = useAlertActions();
  const [hasCleared, setHasCleared] = useState(false);
  const status = startupLogsAlert?.status;

  const handleClear = useEvent(() => {
    clearStartupLogsAlert();
    setHasCleared(true);
  });

  const isDone = status === "done";
  const isRunning = status === "start" || status === "append";

  useEffect(() => {
    let timeout: number | undefined;

    if (isDone) {
      // Dismiss after 5 seconds
      timeout = window.setTimeout(() => handleClear(), 5000);
    }

    return () => {
      if (timeout) {
        window.clearTimeout(timeout);
      }
    };
  }, [isDone]);

  if (startupLogsAlert === null || hasCleared) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4 mb-5 fixed top-5 left-12 min-w-[400px] max-w-[600px] z-200 opacity-95">
      <Banner
        kind="info"
        className="flex flex-col rounded py-3 px-5 animate-in slide-in-from-left"
      >
        <div className="flex justify-between">
          <span className="font-bold text-lg flex items-center mb-2">
            <BoxIcon className="w-5 h-5 inline-block mr-2" />
            {isRunning ? "Initializing..." : "Initialized"}
          </span>
          <Button
            variant="text"
            data-testid="remove-startup-logs-button"
            size="icon"
            onClick={handleClear}
          >
            <XIcon className="w-5 h-5" />
          </Button>
        </div>
        <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground text-base">
          <div className="w-full">
            <pre className="bg-muted p-3 rounded text-sm font-mono overflow-auto max-h-64 whitespace-pre-wrap">
              {startupLogsAlert.content || "Starting startup script..."}
            </pre>
          </div>
        </div>
      </Banner>
    </div>
  );
};
