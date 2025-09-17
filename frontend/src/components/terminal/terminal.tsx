/* Copyright 2024 Marimo. All rights reserved. */

import { AttachAddon } from "@xterm/addon-attach";
import { CanvasAddon } from "@xterm/addon-canvas";
import { FitAddon } from "@xterm/addon-fit";
import { SearchAddon } from "@xterm/addon-search";
import { Unicode11Addon } from "@xterm/addon-unicode11";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { Terminal } from "@xterm/xterm";
import React, { useEffect, useMemo, useRef, useState } from "react";
import "@xterm/xterm/css/xterm.css";
import "./xterm.css";
import {
  ClipboardPasteIcon,
  CopyIcon,
  TextSelectionIcon,
  Trash2Icon,
} from "lucide-react";
import useEvent from "react-use-event-hook";
import { waitForConnectionOpen } from "@/core/network/connection";
import { useRuntimeManager } from "@/core/runtime/config";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import { MinimalHotkeys } from "../shortcuts/renderShortcut";
import { createTerminalTheme } from "./theme";

interface TerminalButtonProps {
  onClick: () => void;
  disabled?: boolean;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  keyboardShortcut?: string;
}

const TerminalButton: React.FC<TerminalButtonProps> = ({
  onClick,
  disabled = false,
  icon: Icon,
  children,
  keyboardShortcut,
}) => (
  <button
    className={cn(
      "w-full text-left px-3 py-2 text-sm flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted",
    )}
    type="button"
    onClick={onClick}
    disabled={disabled}
  >
    <Icon className="w-4 h-4" />
    {children}
    {keyboardShortcut && (
      <MinimalHotkeys className="ml-auto" shortcut={keyboardShortcut} />
    )}
  </button>
);

interface TerminalComponentProps {
  visible: boolean;
  onClose: () => void;
}

interface Position {
  x: number;
  y: number;
}

// Keyboard shortcut handlers
function createKeyboardHandler(terminal: Terminal, _searchAddon: SearchAddon) {
  return (event: KeyboardEvent) => {
    const { ctrlKey, metaKey, key } = event;
    const modifier = ctrlKey || metaKey;

    if (modifier) {
      switch (key) {
        case "c":
          if (terminal.hasSelection()) {
            event.preventDefault();
            void copyToClipboard(terminal.getSelection());
          }
          break;
        case "v":
          event.preventDefault();
          void navigator.clipboard.readText().then((text) => {
            terminal.paste(text);
          });
          break;
        case "a":
          event.preventDefault();
          terminal.selectAll();
          break;
        case "l":
          event.preventDefault();
          terminal.clear();
          break;
      }
    }
  };
}

// Context menu actions
function createContextMenuActions(
  terminal: Terminal,
  setContextMenu: (menu: { x: number; y: number } | null) => void,
) {
  const closeMenu = () => setContextMenu(null);

  return {
    handleCopy: () => {
      if (terminal.hasSelection()) {
        navigator.clipboard.writeText(terminal.getSelection());
      }
      closeMenu();
    },
    handlePaste: () => {
      navigator.clipboard.readText().then((text) => {
        terminal.paste(text);
      });
      closeMenu();
    },
    handleSelectAll: () => {
      terminal.selectAll();
      closeMenu();
    },
    handleClear: () => {
      terminal.clear();
      closeMenu();
    },
    closeMenu,
  };
}

const RESIZE_DEBOUNCE_TIME = 100;

const TerminalComponent: React.FC<TerminalComponentProps> = ({
  visible,
  onClose,
}) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // eslint-disable-next-line react/hook-use-state
  const [{ terminal, fitAddon, searchAddon }] = useState(() => {
    // Create a new terminal instance
    const term = new Terminal({
      fontFamily:
        "Menlo, DejaVu Sans Mono, Consolas, Lucida Console, monospace",
      fontSize: 14,
      scrollback: 10000,
      cursorBlink: true,
      cursorStyle: "block",
      allowTransparency: false,
      theme: createTerminalTheme("dark"),
      rightClickSelectsWord: true,
      wordSeparator: " \t\r\n\"'`(){}[]<>|&;",
      allowProposedApi: true,
    });

    // Load essential addons
    const fitAddon = new FitAddon();
    const searchAddon = new SearchAddon();
    const canvasAddon = new CanvasAddon();
    const unicode11Addon = new Unicode11Addon();
    const webLinksAddon = new WebLinksAddon();

    term.loadAddon(fitAddon);
    term.loadAddon(searchAddon);
    term.loadAddon(canvasAddon);
    term.loadAddon(unicode11Addon);
    term.loadAddon(webLinksAddon);

    // Set Unicode version
    term.unicode.activeVersion = "11";

    return { terminal: term, fitAddon, searchAddon };
  });

  const [initialized, setInitialized] = React.useState(false);
  const [contextMenu, setContextMenu] = useState<Position | null>(null);
  const runtimeManager = useRuntimeManager();

  // Keyboard shortcuts handler
  const handleKeyDown = useEvent(createKeyboardHandler(terminal, searchAddon));

  // Context menu handler
  const handleContextMenu = useEvent((event: MouseEvent) => {
    event.preventDefault();
    setContextMenu({ x: event.clientX, y: event.clientY });
  });

  // Close context menu on click outside
  const handleClickOutside = useEvent((event: MouseEvent) => {
    const target = event.target;
    const isInsideContextMenu =
      target &&
      target instanceof HTMLElement &&
      target.closest(".xterm-context-menu");
    if (contextMenu && !isInsideContextMenu) {
      setContextMenu(null);
    }
  });

  const handleBackendResizeDebounced = useDebouncedCallback(
    ({ cols, rows }: { cols: number; rows: number }) => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        Logger.debug("Sending resize to backend terminal", { cols, rows });
        wsRef.current.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    },
    RESIZE_DEBOUNCE_TIME,
  );

  const handleResize = useEvent(() => {
    if (!terminal || !fitAddon) return;
    fitAddon.fit();
  });

  // Context menu actions
  const { handleCopy, handlePaste, handleSelectAll, handleClear } = useMemo(
    () => createContextMenuActions(terminal, setContextMenu),
    [terminal],
  );

  // Websocket Connection
  useEffect(() => {
    if (initialized) {
      return;
    }

    const connectTerminal = async () => {
      try {
        await waitForConnectionOpen();

        const socket = new WebSocket(runtimeManager.getTerminalWsURL());
        const attachAddon = new AttachAddon(socket);
        terminal.loadAddon(attachAddon);
        wsRef.current = socket;

        const handleDisconnect = () => {
          onClose();
          // Reset
          attachAddon.dispose();
          wsRef.current = null;
          terminal.clear();
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

    // Initial fit with delay to ensure DOM is ready
    setTimeout(() => {
      fitAddon.fit();
    }, RESIZE_DEBOUNCE_TIME);

    terminal.focus();

    const abortController = new AbortController();

    // Add event listeners
    window.addEventListener("resize", handleResize, {
      signal: abortController.signal,
    });
    terminalRef.current.addEventListener("keydown", handleKeyDown, {
      signal: abortController.signal,
    });
    terminalRef.current.addEventListener("contextmenu", handleContextMenu, {
      signal: abortController.signal,
    });
    terminal.onResize(handleBackendResizeDebounced);
    document.addEventListener("click", handleClickOutside, {
      signal: abortController.signal,
    });

    return () => {
      abortController.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className={"relative w-full h-[calc(100%-4px)] bg-popover"}>
      <div className="w-full h-full" ref={terminalRef} />
      {contextMenu && (
        <div
          className={
            "xterm-context-menu fixed z-50 rounded-md shadow-lg py-1 min-w-[160px] border bg-popover"
          }
          style={{
            left: contextMenu.x,
            top: contextMenu.y,
          }}
        >
          <TerminalButton
            onClick={handleCopy}
            disabled={!terminal.hasSelection()}
            icon={CopyIcon}
            keyboardShortcut="mod-c"
          >
            Copy
          </TerminalButton>
          <TerminalButton
            onClick={handlePaste}
            icon={ClipboardPasteIcon}
            keyboardShortcut="mod-v"
          >
            Paste
          </TerminalButton>
          <hr className={cn("my-1 border-border")} />
          <TerminalButton
            onClick={handleSelectAll}
            icon={TextSelectionIcon}
            keyboardShortcut="mod-a"
          >
            Select all
          </TerminalButton>
          <TerminalButton
            onClick={handleClear}
            icon={Trash2Icon}
            keyboardShortcut="mod-l"
          >
            Clear terminal
          </TerminalButton>
        </div>
      )}
    </div>
  );
};

export default React.memo(TerminalComponent);
