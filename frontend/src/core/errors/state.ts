/* Copyright 2023 Marimo. All rights reserved. */

import { atom } from "jotai";

interface BannerState {
  title: string;
  description: string;
  variant?: "danger";
}

export const bannerAtom = atom<BannerState | undefined>(undefined);
