/* Copyright 2024 Marimo. All rights reserved. */
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
  const [status, setStatus] = React.useState<ScriptStatus>();

  React.useEffect(() => {
    let script: HTMLScriptElement | null = document.querySelector(
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

    if (script) {
      const domStatus = script.dataset.status;
      if (domStatus) {
        setStatus(domStatus as ScriptStatus);
        const observer = observeScript(script);
        return () => observer.disconnect();
      }
    } else {
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
    setStatus("unknown");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  return status;
}
