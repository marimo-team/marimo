/* Copyright 2026 Marimo. All rights reserved. */
import React from "react";

type ScriptStatus = "loading" | "ready" | "error" | "unknown";
interface ScriptOptions {
  removeOnUnmount?: boolean;
}

const defaultOptions = { removeOnUnmount: false };

export function useScript(
  src: string,
  options: ScriptOptions = defaultOptions,
) {
  const [status, setStatus] = React.useState<ScriptStatus>(() => {
    const existingScript = document.querySelector<HTMLScriptElement>(
      `script[src="${src}"]`,
    );
    return (existingScript?.dataset.status as ScriptStatus) || "unknown";
  });

  React.useEffect(() => {
    let script = document.querySelector<HTMLScriptElement>(
      `script[src="${src}"]`,
    );

    const updateStatus = (newStatus: ScriptStatus) => {
      if (script) {
        script.dataset.status = newStatus;
        setStatus(newStatus);
      }
    };

    const handleScriptLoad = () => updateStatus("ready");
    const handleScriptError = () => updateStatus("error");

    // observes DOM changes and updates the status
    const observeScript = (script: HTMLScriptElement) => {
      const observer = new MutationObserver(() => {
        const newStatus = script.dataset.status;
        if (newStatus) {
          setStatus(newStatus as ScriptStatus);
        }
      });
      observer.observe(script, {
        attributes: true,
        attributeFilter: ["data-status"],
      });
      return observer;
    };

    if (!script) {
      script = document.createElement("script");
      script.src = src;
      script.async = true;
      updateStatus("loading");
      document.body.append(script);

      script.addEventListener("load", handleScriptLoad);
      script.addEventListener("error", handleScriptError);

      const observer = observeScript(script);

      return () => {
        observer.disconnect();
        if (script) {
          script.removeEventListener("load", handleScriptLoad);
          script.removeEventListener("error", handleScriptError);

          if (options.removeOnUnmount) {
            script.remove();
          }
        }
      };
    }

    const domStatus = script.dataset.status;
    if (domStatus) {
      if (domStatus === "ready" || domStatus === "error") {
        return;
      }
      const observer = observeScript(script);
      return () => observer.disconnect();
    }

    setStatus("unknown");
  }, [src, options.removeOnUnmount]);

  return status;
}
