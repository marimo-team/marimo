/* Copyright 2023 Marimo. All rights reserved. */
import { atom, useAtom } from "jotai";
import { UserConfig, getAppConfig } from "../config";

/**
 * Atom for storing the user config.
 */
const userConfigAtom = atom<UserConfig>(getAppConfig());

/**
 * Returns the user config.
 */
export function useUserConfig() {
  return useAtom(userConfigAtom);
}
