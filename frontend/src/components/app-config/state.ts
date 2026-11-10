/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useSetAtom } from "jotai";
import type { AiSettingsSubTab } from "./ai-config";
import {
  activeUserConfigCategoryAtom,
  type SettingCategoryId,
} from "./user-config-form";

export const aiSettingsSubTabAtom = atom<AiSettingsSubTab>("ai-features");

export const settingDialogAtom = atom<boolean>(false);

export function useOpenSettingsToTab() {
  const setActiveCategory = useSetAtom(activeUserConfigCategoryAtom);
  const setSettingsDialog = useSetAtom(settingDialogAtom);
  const setAiSubTab = useSetAtom(aiSettingsSubTabAtom);

  // Note: If more settings categories need sub-tabs or deep-linking is required,
  // consider using a different strategy like query params
  const handleClick = (tab: SettingCategoryId, subTab?: AiSettingsSubTab) => {
    setActiveCategory(tab);
    if (tab === "ai") {
      setAiSubTab(subTab ?? "ai-features");
    }
    setSettingsDialog(true);
  };
  return { handleClick };
}
