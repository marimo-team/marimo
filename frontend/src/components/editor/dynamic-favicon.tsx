/* Copyright 2024 Marimo. All rights reserved. */

import { usePrevious } from "@dnd-kit/utilities";
import { useEffect } from "react";
import { useCellErrors } from "@/core/cells/cells";
import { useEventListener } from "@/hooks/useEventListener";
import successFaviconUrl from "../../assets/circle-check.ico";
import runningFaviconUrl from "../../assets/circle-play.ico";
import errorFaviconUrl from "../../assets/circle-x.ico";

const FAVICON_PATHS = {
  idle: "./favicon.ico",
  success: successFaviconUrl,
  running: runningFaviconUrl,
  error: errorFaviconUrl,
} as const;

// Cache favicon object URLs lazily
type FaviconKey = keyof typeof FAVICON_PATHS;

async function getFaviconUrl(key: FaviconKey): Promise<string> {
  return FAVICON_PATHS[key];
}

interface Props {
  isRunning: boolean;
}

function maybeSendNotification(numErrors: number) {
  if (document.visibilityState === "visible") {
    return;
  }

  const sendNotification = async () => {
    if (numErrors === 0) {
      new Notification("Execution completed", {
        body: "Your notebook run completed successfully.",
        icon: await getFaviconUrl("success"),
      });
    } else {
      new Notification("Execution failed", {
        body: `Your notebook run encountered ${numErrors} error(s).`,
        icon: await getFaviconUrl("error"),
      });
    }
  };

  if (!("Notification" in window) || Notification.permission === "denied") {
    // Return
  } else if (Notification.permission === "granted") {
    sendNotification();
  } else if (Notification.permission === "default") {
    // We need to ask the user for permission
    Notification.requestPermission().then((permission) => {
      // If the user accepts, let's create a notification
      if (permission === "granted") {
        sendNotification();
      }
    });
  }
}

export const DynamicFavicon = (props: Props) => {
  const { isRunning } = props;
  const errors = useCellErrors();

  let favicon: HTMLLinkElement | null =
    document.querySelector("link[rel~='icon']");

  if (!favicon) {
    favicon = document.createElement("link");
    favicon.rel = "icon";
    document.getElementsByTagName("head")[0].append(favicon);
  }

  useEffect(() => {
    // No change on startup (autorun enabled or not)
    // Treat the default marimo favicon as "idle"
    if (!isRunning && favicon.href.includes("favicon")) {
      return;
    }

    const updateFavicon = async () => {
      let key: FaviconKey;
      // When notebook is running, display running favicon
      if (isRunning) {
        key = "running";
      } else {
        // When run is complete, display success or error favicon
        key = errors.length === 0 ? "success" : "error";
      }
      favicon.href = await getFaviconUrl(key);

      // If notebook is in focus, reset favicon after 3 seconds
      // If not in focus, the focus event listener handles it
      if (!document.hasFocus()) {
        return;
      }

      const timeoutId = setTimeout(async () => {
        favicon.href = await getFaviconUrl("idle");
      }, 3000);

      return () => clearTimeout(timeoutId);
    };

    updateFavicon();
  }, [isRunning, errors, favicon]);

  // Send user notification when run has completed
  const prevRunning = usePrevious(isRunning) ?? isRunning;
  useEffect(() => {
    if (prevRunning && !isRunning) {
      maybeSendNotification(errors.length);
    }
  }, [errors, prevRunning, isRunning]);

  // When notebook comes back in focus, reset favicon
  useEventListener(window, "focus", async (_) => {
    if (!isRunning) {
      favicon.href = await getFaviconUrl("idle");
    }
  });

  return null;
};
