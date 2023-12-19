/* Copyright 2023 Marimo. All rights reserved. */
import * as Y from "yjs";
import { WebrtcProvider } from "y-webrtc";

export const ydoc = new Y.Doc();
export const provider = new WebrtcProvider("marimo", ydoc);
