/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue } from "jotai";
import { createReducerAndAtoms } from "@/utils/createReducer";
import type { Identified } from "@/utils/typed";
import { generateUUID } from "@/utils/uuid";
import type { Banner } from "../kernel/messages";

/**
 * Atom for storing kernel startup error message.
 * When set to a non-null value, shows a modal with the error details.
 */
export const kernelStartupErrorAtom = atom<string | null>(null);

interface BannerState {
  banners: Identified<Banner>[];
}

const { valueAtom: bannersAtom, useActions } = createReducerAndAtoms(
  () => ({ banners: [] }) as BannerState,
  {
    addBanner: (state, banner: Banner) => {
      return {
        ...state,
        banners: [...state.banners, { ...banner, id: generateUUID() }],
      };
    },
    removeBanner: (state, id: string) => {
      return {
        ...state,
        banners: state.banners.filter((banner) => banner.id !== id),
      };
    },
    clearBanners: (state) => {
      return { ...state, banners: [] };
    },
  },
);

/**
 * React hook to get the Banner state.
 */
export const useBanners = () => useAtomValue(bannersAtom);

/**
 * React hook to get the Banners actions.
 */
export function useBannersActions() {
  return useActions();
}
