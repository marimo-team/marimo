/* Copyright 2026 Marimo. All rights reserved. */
import { useCallback, useSyncExternalStore } from "react";

type ScriptStatus = "loading" | "ready" | "error" | "unknown";
interface ScriptOptions {
  removeOnUnmount?: boolean;
}

interface ScriptEntry {
  element: HTMLScriptElement;
  listeners: Set<() => void>;
  /** Whether useScript created the element, and so may remove it. */
  owned: boolean;
}

const defaultOptions = { removeOnUnmount: false };

// One entry per src, so reading the status on render is a map lookup
const scripts = new Map<string, ScriptEntry>();

function findScript(src: string): HTMLScriptElement | undefined {
  // Compare attributes rather than building a selector, which `src` could break
  return [...document.scripts].find(
    (script) => script.getAttribute("src") === src,
  );
}

function acquireScript(src: string): ScriptEntry {
  const cached = scripts.get(src);
  if (cached?.element.isConnected) {
    return cached;
  }
  const existing = findScript(src);
  const element = existing ?? document.createElement("script");
  const entry: ScriptEntry = {
    element,
    listeners: new Set(),
    owned: !existing,
  };
  const setStatus = (status: ScriptStatus) => {
    element.dataset.status = status;
    entry.listeners.forEach((listener) => listener());
  };
  // Listen for the script's lifetime rather than per subscriber, so the
  // status still settles if the first subscriber unmounts mid-load.
  element.addEventListener("load", () => setStatus("ready"), { once: true });
  element.addEventListener("error", () => setStatus("error"), { once: true });
  if (!existing) {
    element.src = src;
    element.async = true;
    element.dataset.status = "loading";
    document.body.append(element);
  }
  scripts.set(src, entry);
  return entry;
}

export function useScript(
  src: string,
  options: ScriptOptions = defaultOptions,
) {
  const { removeOnUnmount } = options;
  const getSnapshot = useCallback((): ScriptStatus => {
    const cached = scripts.get(src)?.element;
    const element = cached?.isConnected ? cached : findScript(src);
    return (element?.dataset.status as ScriptStatus) || "unknown";
  }, [src]);

  const subscribe = useCallback(
    (onChange: () => void) => {
      const entry = acquireScript(src);
      entry.listeners.add(onChange);
      return () => {
        entry.listeners.delete(onChange);
        if (removeOnUnmount && entry.owned && entry.listeners.size === 0) {
          entry.element.remove();
          if (scripts.get(src) === entry) {
            scripts.delete(src);
          }
        }
      };
    },
    [src, removeOnUnmount],
  );

  return useSyncExternalStore(subscribe, getSnapshot);
}
