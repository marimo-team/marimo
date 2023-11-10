/* Copyright 2023 Marimo. All rights reserved. */
interface Script {
  element: HTMLScriptElement;
  loaded: boolean;
}

const LOADED_SCRIPTS: Record<string, Script> = {};

export function lookupScript(src: string) {
  return src in LOADED_SCRIPTS ? LOADED_SCRIPTS[src] : null;
}

export function updateScriptCache(src: string, value: Script) {
  LOADED_SCRIPTS[src] = value;
}
