/* Copyright 2023 Marimo. All rights reserved. */
import * as Y from "yjs";
import { yCollab } from "y-codemirror.next";
import { provider, ydoc } from "./provider";
import { CellId } from "../cells/ids";

const usercolors = [
  { color: "#30bced", light: "#30bced33" },
  { color: "#6eeb83", light: "#6eeb8333" },
  { color: "#ffbc42", light: "#ffbc4233" },
  { color: "#ecd444", light: "#ecd44433" },
  { color: "#ee6352", light: "#ee635233" },
  { color: "#9ac2c9", light: "#9ac2c933" },
  { color: "#8acb88", light: "#8acb8833" },
  { color: "#1be7ff", light: "#1be7ff33" },
];

// select a random color for this user
const random = Math.floor(Math.random() * 100);
const userColor = usercolors[random % usercolors.length];

provider.awareness.setLocalStateField("user", {
  // TODO: get username from {{marimo-user}}
  name: `Anonymous ${Math.floor(Math.random() * 100)}`,
  color: userColor.color,
  colorLight: userColor.light,
});

export function collabExtension(cellId: CellId) {
  // const initialText = ydoc
  //   .getMap<any>("root")
  //   .get("cellData")
  //   .get(cellId)
  //   .get("code");

  const yCellCode = ydoc.getText(`root.${cellId}.code`);

  const undoManager = new Y.UndoManager(yCellCode);
  return yCollab(yCellCode, provider.awareness, { undoManager });
}
