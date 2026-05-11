/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";

export interface DownloadSizeLimit {
  limitBytes: number;
  unavailableMessage: string;
}

export const downloadSizeLimitAtom = atom<DownloadSizeLimit | null>(null);
