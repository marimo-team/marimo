/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { Capabilities } from "../kernel/messages";
import { store } from "../state/jotai";

export const capabilitiesAtom = atom<Capabilities>({
  terminal: false,
  pylsp: false,
  basedpyright: false,
  ty: false,
  pyrefly: false,
});

export function hasCapability(key: keyof Capabilities): boolean {
  return store.get(capabilitiesAtom)?.[key] ?? false;
}
