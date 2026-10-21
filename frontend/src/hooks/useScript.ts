/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useSyncExternalStore } from "react";

type ScriptStatus = "loading" | "ready" | "error" | "unknown";
interface ScriptOptions {
  removeOnUnmount?: boolean;
}

const defaultOptions = { removeOnUnmount: false };

export function useScript(
  src: string,
  options: ScriptOptions = defaultOptions,
) {
  const { removeOnUnmount } = options;
  const getSnapshot = useCallback((): ScriptStatus => {
    const script = document.querySelector<HTMLScriptElement>(
      `script[src="${src}"]`,
    );
    return (script?.dataset.status as ScriptStatus) || "unknown";
  }, [src]);

  const subscribe = useCallback(
    (onChange: () => void) => {
      let script = document.querySelector<HTMLScriptElement>(
        `script[src="${src}"]`,
      );
      const created = !script;
      if (!script) {
        script = document.createElement("script");
        script.src = src;
        script.async = true;
        script.dataset.status = "loading";
      }
      const element = script;
      const handleLoad = () => {
        element.dataset.status = "ready";
      };
      const handleError = () => {
        element.dataset.status = "error";
      };
      const observer = new MutationObserver(onChange);
      observer.observe(element, {
        attributes: true,
        attributeFilter: ["data-status"],
      });
      if (created) {
        element.addEventListener("load", handleLoad);
        element.addEventListener("error", handleError);
        document.body.append(element);
      }
      return () => {
        observer.disconnect();
        if (created) {
          element.removeEventListener("load", handleLoad);
          element.removeEventListener("error", handleError);
          if (removeOnUnmount) {
            element.remove();
          }
        }
      };
    },
    [src, removeOnUnmount],
  );

  return useSyncExternalStore(subscribe, getSnapshot);
}
