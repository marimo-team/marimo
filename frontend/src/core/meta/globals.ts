/* Copyright 2024 Marimo. All rights reserved. */
import { marimoVersionAtom, serverTokenAtom } from "@/core/meta/state";
import { store } from "@/core/state/jotai";

/**
 * This should be avoided and instead use the store.
 */
export const getMarimoVersion = () => store.get(marimoVersionAtom);
/**
 * This should be avoided and instead use the store.
 */
export const getMarimoServerToken = () => store.get(serverTokenAtom);

/**
 * N.B This still exists for backwards compatibility.
 * Some code paths still look for the marimo-code html tag.
 */
export const getMarimoCode = (): string | undefined => {
  const tag = document.querySelector("marimo-code");
  if (!tag) {
    return undefined;
  }
  const inner = tag.innerHTML;
  return decodeURIComponent(inner).trim();
};
