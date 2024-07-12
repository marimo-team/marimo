/* Copyright 2024 Marimo. All rights reserved. */
import { Strings } from "@/utils/strings";
import React, { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { AttachAddon } from "@xterm/addon-attach";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import "./xterm.css";

const TerminalComponent = () => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);

  useEffect(() => {
    if (!terminalRef.current || terminal.current) {
      return;
    }

    // Create a new terminal instance
    const term = new Terminal({});
    terminal.current = term;
    // Add extra addons
    const socket = new WebSocket(createWsUrl());
    const attachAddon = new AttachAddon(socket);
    const fitAddon = new FitAddon();
    terminal.current.loadAddon(fitAddon);
    terminal.current.loadAddon(attachAddon);

    // Handle resize
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener("resize", handleResize);

    // Open terminal
    term.open(terminalRef.current);
    fitAddon.fit();
    term.focus();

    return () => {
      terminal.current?.dispose();
      window.removeEventListener("resize", handleResize);
    };
  }, []);

  return (
    <div className="relative w-full h-[calc(100%-4px)] dark bg-[var(--slate-1)]">
      <div className="w-full h-full" ref={terminalRef} />
    </div>
  );
};

export function createWsUrl(): string {
  const baseURI = document.baseURI;

  const url = new URL(baseURI);
  const protocol = url.protocol === "https:" ? "wss" : "ws";
  url.protocol = protocol;
  url.pathname = `${Strings.withoutTrailingSlash(url.pathname)}/terminal/ws`;

  return url.toString();
}

export default React.memo(TerminalComponent);
