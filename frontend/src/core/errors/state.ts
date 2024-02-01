/* Copyright 2024 Marimo. All rights reserved. */

import { createReducer } from "@/utils/createReducer";
import { atom, useAtomValue, useSetAtom } from "jotai";
import { useMemo } from "react";

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

const { reducer, createActions } = createReducer(
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

const bannersAtom = atom<BannerState>({ banners: [] });

/**
 * React hook to get the Banner state.
 */
export const useBanners = () => useAtomValue(bannersAtom);

/**
 * React hook to get the Banners actions.
 */
export function useBannersActions() {
  const setState = useSetAtom(bannersAtom);
  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => reducer(state, action));
    });
    return actions;
  }, [setState]);
}
