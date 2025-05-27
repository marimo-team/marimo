/* Copyright 2024 Marimo. All rights reserved. */
import { atomWithStorage } from "jotai/utils";
import { getFeatureFlag } from "../config/feature-flag";
import { once } from "lodash-es";

/**
 * The username for the current user when using real-time collaboration.
 * This is stored in localStorage.
 */
export const usernameAtom = atomWithStorage<string>("marimo:rtc:username", "");

/**
 * Whether RTC is enabled.
 *
 * This is cached on page-load because this UI can get into
 * weird states, so we require a page reload to take effect.
 */
export const isRtcEnabled = once(() => {
  return getFeatureFlag("rtc_v2");
});
