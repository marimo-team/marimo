/* Copyright 2024 Marimo. All rights reserved. */
import { Strings } from "@/utils/strings";
import React, { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { AttachAddon } from "@xterm/addon-attach";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import "./xterm.css";

const TerminalComponent: React.FC<{
  visible: boolean;
  onClose: () => void;
}> = ({ visible, onClose }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line react/hook-use-state
  const [{ terminal, fitAddon }] = useState(() => {
    // Create a new terminal instance
    const term = new Terminal({});
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    return { terminal: term, fitAddon };
  });
  const [initialized, setInitialized] = React.useState(false);

  // Websocket Connection
  useEffect(() => {
    if (initialized) {
      return;
    }

    const socket = new WebSocket(createWsUrl());
    const attachAddon = new AttachAddon(socket);
    terminal.loadAddon(attachAddon);

    const handleDisconnect = () => {
      onClose();
      // Reset
      attachAddon.dispose();
      terminal.clear();
      setInitialized(false);
    };

    socket.addEventListener("close", handleDisconnect);
    setInitialized(true);

    return () => {
      // noop
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialized]);

  // When visible
  useEffect(() => {
    if (visible) {
      fitAddon.fit();
      terminal.focus();
    }

    return;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);

  // On mount
  useEffect(() => {
    if (!terminalRef.current) {
      return;
    }

    terminal.open(terminalRef.current);
    fitAddon.fit();
    terminal.focus();
    // Handle resize
    const handleResize = () => {
      fitAddon.fit();
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
