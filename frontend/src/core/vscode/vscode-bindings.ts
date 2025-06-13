/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { KnownQueryParams } from "../constants";
import { isPlatformMac } from "../hotkeys/shortcuts";
import { isWasm } from "../wasm/utils";

export const isEmbedded =
  // eslint-disable-next-line ssr-friendly/no-dom-globals-in-module-scope
  typeof window !== "undefined" && window.parent !== window;

// To enable keyboard shortcuts of VS Code when the iframe is focused,
// we have to dispatch keyboard events in the parent window.
// See https://github.com/microsoft/vscode/issues/65452#issuecomment-586036474
export function maybeRegisterVSCodeBindings() {
  const isVscode = new URLSearchParams(window.location.search).has(
    KnownQueryParams.vscode,
  );
  if (!isVscode) {
    return;
  }

  if (!isEmbedded || isWasm()) {
    return;
  }

  Logger.log("[vscode] Registering VS Code bindings");
  registerKeyboard();
  registerCopyPaste();
  registerOpenExternalLink();
  registerContextMenu();
}

function registerCopyPaste() {
  window.addEventListener("copy", () => {
    const selection = window.getSelection()?.toString() ?? "";
    sendToPanelManager({
      command: "copy",
      text: selection,
    });
  });

  window.addEventListener("cut", () => {
    const selection = window.getSelection()?.toString() ?? "";
    // Only run this on mac
    if (isPlatformMac()) {
      // clear
      document.execCommand("insertText", false, "");
    }
    sendToPanelManager({
      command: "cut",
      text: selection,
    });
  });

  window.addEventListener("message", async (event) => {
    try {
      const message = event.data;
      const isMac = isPlatformMac();
      switch (message.command) {
        case "paste":
          Logger.log(`[vscode] Received paste mac=${isMac}`, message);
          if (isMac) {
            const el = document.activeElement;
            if (!el) {
              Logger.warn("[vscode] No active element to paste into");
              // execCommand has finally been removed (since being deprecated)
              // https://github.com/microsoft/vscode/issues/239228
              document.execCommand("insertText", false, message.text);
              return;
            }
            const dt = new DataTransfer();
            dt.setData("text/plain", message.text);
            el.dispatchEvent(
              new ClipboardEvent("paste", { clipboardData: dt }),
            );
          } else {
            Logger.log("[vscode] Not pasting on mac");
          }
          return;
      }
    } catch (error) {
      Logger.error("Error in paste message handler", error);
    }
  });
}

function registerKeyboard() {
  document.addEventListener("keydown", (event) => {
    // Copy
    if ((event.ctrlKey || event.metaKey) && event.key === "c") {
      const selection = window.getSelection()?.toString() ?? "";
      Logger.log("[vscode] Sending copy", selection);
      sendToPanelManager({
        command: "copy",
        text: selection,
      });
      return;
    }
    // Cut
    if ((event.ctrlKey || event.metaKey) && event.key === "x") {
      const selection = window.getSelection()?.toString() ?? "";
      // clear
      if (isPlatformMac()) {
        document.execCommand("insertText", false, "");
      }
      Logger.log("[vscode] Sending cut", selection);
      sendToPanelManager({
        command: "cut",
        text: selection,
      });
      return;
    }
    // Paste
    if ((event.ctrlKey || event.metaKey) && event.key === "v") {
      Logger.log("[vscode] Sending paste");
      sendToPanelManager({
        command: "paste",
      });
      return;
    }
  });
}

function registerOpenExternalLink() {
  document.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    if (target.tagName !== "A") {
      return;
    }
    const href = target.getAttribute("href");
    if (!href) {
      return;
    }
    if (href.startsWith("http://") || href.startsWith("https://")) {
      event.preventDefault();
      sendToPanelManager({
        command: "external_link",
        url: href,
      });
    }
  });
}

function registerContextMenu() {
  document.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    sendToPanelManager({
      command: "context_menu",
    });
  });
}

export function sendToPanelManager(msg: VscodeMessage) {
  window.parent?.postMessage(msg, "*");
}

export type VscodeMessage =
  | {
      command: "context_menu";
    }
  | {
      command: "paste";
    }
  | {
      command: "copy";
      text: string;
    }
  | {
      command: "cut";
      text: string;
    }
  | {
      command: "external_link";
      url: string;
    };
