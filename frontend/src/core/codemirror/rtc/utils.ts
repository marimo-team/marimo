/* Copyright 2024 Marimo. All rights reserved. */

export const rtcLogger = (...args: unknown[]) => {
  // eslint-disable-next-line no-console
  console.warn("[debug][rtc]", ...args);
};
