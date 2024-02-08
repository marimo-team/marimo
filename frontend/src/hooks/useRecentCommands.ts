/* Copyright 2024 Marimo. All rights reserved. */
import { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { useLocalStorage } from "./useLocalStorage";

const MAX_RECENT_COMMANDS = 3;
type RecentCommandId = HotkeyAction | (string & {});

export function useRecentCommands() {
  const [commands, setCommands] = useLocalStorage<RecentCommandId[]>(
    "marimo:commands",
    [],
  );

  return {
    recentCommands: commands,
    addRecentCommand: (command: RecentCommandId) => {
      const uniqueCommands = unique([command, ...commands]);
      setCommands(uniqueCommands.slice(0, MAX_RECENT_COMMANDS));
    },
  };
}

function unique<T>(xs: T[]): T[] {
  return [...new Set(xs)];
}
