/* Copyright 2024 Marimo. All rights reserved. */
import { atom } from "jotai";
import type { Capabilities } from "../kernel/messages";

export const capabilitiesAtom = atom<Capabilities>({
  terminal: false,
});
