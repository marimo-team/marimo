/* Copyright 2024 Marimo. All rights reserved. */
import { atom, useSetAtom } from "jotai";
import {
  activeUserConfigCategoryAtom,
  type SettingCategoryId,
} from "./user-config-form";

export const settingDialogAtom = atom<boolean>(false);

export function useOpenSettingsToTab() {
  const setActiveCategory = useSetAtom(activeUserConfigCategoryAtom);
  const setSettingsDialog = useSetAtom(settingDialogAtom);
  const handleClick = (tab: SettingCategoryId) => {
    setActiveCategory(tab);
    setSettingsDialog(true);
  };
  return { handleClick };
}
