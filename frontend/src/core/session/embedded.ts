/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import type { StaticNotebookSnapshot } from "../transports/static";

/** The notebook the page was served with, read at mount. Null when none was. */
export const embeddedSnapshotAtom = atom<StaticNotebookSnapshot | null>(null);
