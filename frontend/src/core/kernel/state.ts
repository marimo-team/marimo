/* Copyright 2026 Marimo. All rights reserved. */
import { atom } from "jotai";
import { waitFor } from "../state/jotai";

export interface KernelState {
  isInstantiated: boolean;
  error: Error | null;
}

export const kernelStateAtom = atom<KernelState>({
  isInstantiated: false,
  error: null,
});

export function waitForKernelToBeInstantiated(): Promise<KernelState> {
  return waitFor(kernelStateAtom, (value) => value.isInstantiated);
}
