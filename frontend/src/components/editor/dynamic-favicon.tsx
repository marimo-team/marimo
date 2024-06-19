/* Copyright 2024 Marimo. All rights reserved. */
import { useCellErrors } from "@/core/cells/cells";
import { useEventListener } from "@/hooks/useEventListener";
import { useEffect } from "react";

const FAVICONS = {
  idle: "./favicon.ico",
  success: "./circle-check.ico",
  running: "./circle-play.ico",
  error: "./circle-x.ico",
};

interface Props {
  isRunning: boolean;
}

function maybeSendNotification(numErrors: number) {
  if (document.visibilityState === "visible") {
    return;
  }

  const sendNotification = () => {
    if (numErrors === 0) {
      new Notification("Execution completed", {
        body: "Your notebook run completed successfully.",
        icon: FAVICONS.success,
      });
    } else {
      new Notification("Execution failed", {
        body: `Your notebook run encountered ${numErrors} error(s).`,
        icon: FAVICONS.error,
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
    // When notebook is running, display running favicon
    if (isRunning) {
      favicon.href = FAVICONS.running;
      return;
    }
    // When run is complete, display success or error favicon
    favicon.href = errors.length === 0 ? FAVICONS.success : FAVICONS.error;
    // If notebook is in focus, reset favicon after 3 seconds
    // If not in focus, the focus event listener handles it
    if (!document.hasFocus()) {
      return;
    }
    const timeoutId = setTimeout(() => {
      favicon.href = FAVICONS.idle;
    }, 3000);

    return () => {
      favicon.href = FAVICONS.idle;
      clearTimeout(timeoutId);
    };
  }, [isRunning, errors, favicon]);

  useEffect(() => {
    maybeSendNotification(errors.length);
  }, [errors]);

  // When notebook comes back in focus, reset favicon
  useEventListener(window, "focus", (_) => {
    if (document.visibilityState === "visible" && document.hasFocus()) {
      favicon.href = FAVICONS.idle;
    }
  });

  return null;
};
