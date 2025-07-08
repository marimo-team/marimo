/* Copyright 2024 Marimo. All rights reserved. */

import { AttachAddon } from "@xterm/addon-attach";
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import React, { useEffect, useRef, useState } from "react";
import "@xterm/xterm/css/xterm.css";
import "./xterm.css";
import { waitForConnectionOpen } from "@/core/network/connection";
import { useRuntimeManager } from "@/core/runtime/config";
import { Logger } from "@/utils/Logger";
import { debounce } from "@/utils/debounce";

const TerminalComponent: React.FC<{
  visible: boolean;
  onClose: () => void;
}> = ({ visible, onClose }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal>();
  const fitAddon = useRef<FitAddon>();

  const [initialized, setInitialized] = React.useState(false);
  const runtimeManager = useRuntimeManager();

  // On mount
  useEffect(() => {
    if (terminalRef.current) {
      // Create a new terminal instance
      const term = new Terminal({
        fontFamily:
          "Menlo, DejaVu Sans Mono, Consolas, Lucida Console, monospace",
        fontSize: 14,
        allowProposedApi: true,
      });
      const addon = new FitAddon();
      term.loadAddon(addon);
      term.open(terminalRef.current);

      terminal.current = term;
      fitAddon.current = addon;

      // Handle resize
      const handleResize = debounce(() => {
        fitAddon.current?.fit();
      }, 50);
      window.addEventListener("resize", handleResize);

      return () => {
        window.removeEventListener("resize", handleResize);
        terminal.current?.dispose();
      };
    }
    return;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Websocket Connection
  useEffect(() => {
    if (initialized || !terminal.current) {
      return;
    }

    const connectTerminal = async () => {
      try {
        await waitForConnectionOpen();

        const socket = new WebSocket(runtimeManager.getTerminalWsURL());
        const attachAddon = new AttachAddon(socket);
        terminal.current?.loadAddon(attachAddon);

        const handleDisconnect = () => {
          onClose();
          // Reset
          attachAddon.dispose();
          terminal.current?.clear();
          setInitialized(false);
        };

        socket.addEventListener("close", handleDisconnect);
        setInitialized(true);
      } catch (error) {
        Logger.error("Runtime health check failed for terminal", error);
        onClose();
      }
    };

    connectTerminal();
  }, [initialized, runtimeManager, onClose]);

  // When visible
  useEffect(() => {
    if (visible) {
      fitAddon.current?.fit();
      terminal.current?.focus();
    }
  }, [visible]);

  return (
    <div className="relative w-full h-[calc(100%-4px)] dark bg-[var(--slate-1)]">
      <div className="w-full h-full" ref={terminalRef} />
    </div>
  );
};

export default React.memo(TerminalComponent);
