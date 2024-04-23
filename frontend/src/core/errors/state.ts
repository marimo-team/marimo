/* Copyright 2024 Marimo. All rights reserved. */

import { createReducerAndAtoms } from "@/utils/createReducer";
import { useAtomValue } from "jotai";

interface Banner {
  id: string;
  title: string;
  description: string;
  variant?: "danger";
  action?: "restart";
}

interface BannerState {
  banners: Banner[];
}

const { valueAtom: bannersAtom, useActions } = createReducerAndAtoms(
  () => ({ banners: [] }) as BannerState,
  {
    addBanner: (state, banner: Banner) => {
      return { ...state, banners: [...state.banners, banner] };
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
