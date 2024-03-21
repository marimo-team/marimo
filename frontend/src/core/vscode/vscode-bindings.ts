/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { isPyodide } from "../pyodide/utils";
import { isPlatformMac } from "../hotkeys/shortcuts";

export const isEmbedded =
  // eslint-disable-next-line ssr-friendly/no-dom-globals-in-module-scope
  typeof window !== "undefined" && window.parent !== window;

// To enable keyboard shortcuts of VS Code when the iframe is focused,
// we have to dispatch keyboard events in the parent window.
// See https://github.com/microsoft/vscode/issues/65452#issuecomment-586036474
export function maybeRegisterVSCodeBindings() {
  if (!isEmbedded || isPyodide()) {
    return;
  }
  Logger.log("Registering VS Code bindings");
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

  window.addEventListener("message", (event) => {
    const message = event.data;
    switch (message.command) {
      case "paste":
        if (isPlatformMac()) {
          document.execCommand("insertText", false, message.text);
        }
        return;
    }
  });
}

function registerKeyboard() {
  document.addEventListener("keydown", (event) => {
    // Copy
    if ((event.ctrlKey || event.metaKey) && event.key === "c") {
      const selection = window.getSelection()?.toString() ?? "";
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
      document.execCommand("insertText", false, "");
      sendToPanelManager({
        command: "cut",
        text: selection,
      });
      return;
    }
    // Paste
    if ((event.ctrlKey || event.metaKey) && event.key === "v") {
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

function sendToPanelManager(msg: VscodeMessage) {
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
