/* Copyright 2024 Marimo. All rights reserved. */
import { KnownQueryParams } from "@/core/constants";
import { getSessionId } from "@/core/kernel/session";
import { yCollab } from "y-codemirror.next";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";
import type { CellId } from "@/core/cells/ids";

const cellProviders = new Map<CellId, WebsocketProvider>();

export function realTimeCollaboration(cellId: CellId, initialCode = "") {
  let wsProvider = cellProviders.get(cellId);
  let ytext: Y.Text;

  if (wsProvider) {
    ytext = wsProvider.doc.getText("code");
  } else {
    const ydoc = new Y.Doc();
    ytext = ydoc.getText("code");
    if (initialCode) {
      ytext.insert(0, initialCode);
    }
    // Add file and session_id to the params
    const params: Record<string, string> = {};
    params.session_id = getSessionId();
    const searchParams = new URLSearchParams(window.location.search);
    const filePath = searchParams.get(KnownQueryParams.filePath);
    if (filePath) {
      params.file = filePath;
    }
    wsProvider = new WebsocketProvider("ws", cellId, ydoc, {
      params,
    });
    cellProviders.set(cellId, wsProvider);
  }

  const extension = yCollab(ytext, null);

  return {
    code: ytext.toJSON(),
    extension,
  };
}
