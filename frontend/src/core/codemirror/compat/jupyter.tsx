/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { toast } from "../../../components/ui/use-toast";
import { store } from "@/core/state/jotai";
import { chromeAtom } from "@/components/editor/chrome/state";
import { saveUserConfig } from "@/core/network/requests";
import type { UserConfig } from "@/core/config/config-schema";
import { userConfigAtom } from "@/core/config/config";
import { PACKAGES_INPUT_ID } from "@/components/editor/chrome/panels/constants";

interface ReplaceCommand {
  match: string;
  onMatch: () => void;
  title: string;
  description: React.ReactNode;
}

export function jupyterHelpExtension(): Extension {
  // Function to update the module reload mode
  // Updates local config and saves to server
  const handleUpdateModuleReload = async (mode: "lazy" | "autorun" | "off") => {
    const config = store.get(userConfigAtom);
    const newConfig: UserConfig = {
      ...config,
      runtime: {
        ...config.runtime,
        auto_reload: mode,
      },
    };
    await saveUserConfig({ config: newConfig }).then(() =>
      store.set(userConfigAtom, newConfig),
    );
  };

  const focusPackagesInput = () => {
    requestAnimationFrame(() => {
      const input = document.getElementById(PACKAGES_INPUT_ID);
      if (input) {
        input.focus();
      }
    });
  };

  const commands: ReplaceCommand[] = [
    {
      match: "!pip install",
      onMatch: () => {
        store.set(chromeAtom, (prev) => ({
          ...prev,
          isSidebarOpen: true,
          selectedPanel: "packages",
        }));

        focusPackagesInput();
      },
      title: "Package Installation",
      description: (
        <>
          The package manager sidebar has been opened.
          <br />
          Install packages directly from there instead.
        </>
      ),
    },
    {
      match: "!uv pip install",
      onMatch: () => {
        store.set(chromeAtom, (prev) => ({
          ...prev,
          isSidebarOpen: true,
          selectedPanel: "packages",
        }));

        focusPackagesInput();
      },
      title: "Package Installation",
      description: (
        <>
          The package manager sidebar has been opened.
          <br />
          Install packages directly from there instead.
        </>
      ),
    },
    {
      match: "%load_ext autoreload 2",
      onMatch: async () => {
        await handleUpdateModuleReload("autorun");
      },
      title: "Module reload",
      description: (
        <>
          Module reload mode set to <b>autorun</b> - module changes will re-run
          the cells that import them.
        </>
      ),
    },
    {
      match: "%load_ext autoreload 1",
      onMatch: async () => {
        await handleUpdateModuleReload("lazy");
      },
      title: "Module reload",
      description: (
        <>
          Module reload mode set to <b>lazy</b> - module changes will mark the
          cells that import them as stale.
        </>
      ),
    },
    {
      match: "%load_ext autoreload 0",
      onMatch: async () => {
        await handleUpdateModuleReload("off");
      },
      title: "Module reload",
      description: (
        <>Module reload disabled - module changes will not be detected.</>
      ),
    },
    {
      match: "!ls",
      onMatch: () => {
        // noop
      },
      title: "Listing files",
      description: (
        <>
          Shell commands are not directly supported.
          <br />
          Use <code>sys.subprocess(['ls'])</code> instead.
        </>
      ),
    },
  ];

  const commandMap = new Map(commands.map((cmd) => [cmd.match, cmd]));

  return EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      const cursor = update.state.selection.main;
      // Get text from the start of the line to the cursor
      const doc = update.state.doc;
      const line = doc.lineAt(cursor.head);
      const text = doc.sliceString(line.from, cursor.anchor).trim();

      const cmd = commandMap.get(text);
      if (cmd) {
        // Execute the command
        cmd.onMatch();

        // Show toast
        toast({
          title: cmd.title,
          description: cmd.description,
        });
      }
    }
  });
}
