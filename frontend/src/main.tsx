/* Copyright 2024 Marimo. All rights reserved. */

import { mount } from "@/mount";

declare global {
  interface Window {
    __MARIMO_MOUNT_CONFIG__: unknown;
  }
}

const el = document.getElementById("root");
if (el) {
  if (!globalThis.__MARIMO_MOUNT_CONFIG__) {
    throw new Error("[marimo] mount config not found");
  }
  mount(globalThis.__MARIMO_MOUNT_CONFIG__, el);
} else {
  throw new Error("[marimo] root element not found");
}
