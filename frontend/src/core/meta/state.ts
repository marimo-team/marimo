/* Copyright 2024 Marimo. All rights reserved. */

import { atom } from "jotai";
import { Logger } from "@/utils/Logger";

function getVersionFromMountConfig(): string | null {
  try {
    const mountConfig = globalThis.__MARIMO_MOUNT_CONFIG__ as {
      version: string;
    };
    return mountConfig.version;
  } catch {
    Logger.warn("Failed to get version from mount config");
    return null;
  }
}

const BUILD_VERSION: string =
  getVersionFromMountConfig() ||
  import.meta.env.VITE_MARIMO_VERSION ||
  "unknown";

export const marimoVersionAtom = atom<string>(BUILD_VERSION);

export const showCodeInRunModeAtom = atom<boolean>(true);

export const serverTokenAtom = atom<string | null>(null);
