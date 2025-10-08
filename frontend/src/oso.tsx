/* Copyright 2024 Marimo. All rights reserved. */

import posthog from 'posthog-js'
import { mount } from "@/oso-mount";


declare global {
  interface Window {
    __MARIMO_MOUNT_CONFIG__: unknown;
  }
}

if (import.meta.env.VITE_POSTHOG_PUBLIC_API_KEY) {
  posthog.init(import.meta.env.VITE_POSTHOG_PUBLIC_API_KEY, {
    session_recording: {
      // WARNING: Only enable this if you understand the security implications
      recordCrossOriginIframes: true,
    }
  });
} else {
  console.warn("POSTHOG_PUBLIC_API_KEY not set, skipping posthog init");
}

// eslint-disable-next-line ssr-friendly/no-dom-globals-in-module-scope
const el = document.getElementById("root");
if (el) {
  if (!window.__MARIMO_MOUNT_CONFIG__) {
    throw new Error("[marimo] mount config not found");
  }
  mount(window.__MARIMO_MOUNT_CONFIG__, el).catch((e) => {
    console.error("Failed to mount marimo app", e);
  });
} else {
  throw new Error("[marimo] root element not found");
}
