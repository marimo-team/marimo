/* Copyright 2024 Marimo. All rights reserved. */
import { atomWithStorage } from "jotai/utils";
import { getFeatureFlag } from "../config/feature-flag";

/**
 * The username for the current user when using real-time collaboration.
 * This is stored in localStorage.
 */
export const usernameAtom = atomWithStorage<string>("marimo:rtc:username", "");

/**
 * Whether RTC is enabled.
 */
export function isRtcEnabled() {
  return getFeatureFlag("rtc_v2");
}
