/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { Meta, StoryObj } from "@storybook/react-vite";
import React, { useEffect, useRef, useState } from "react";
import { ReadonlyCode } from "../components/editor/code/readonly-python-code";
import { basicBundle, type CodeMirrorSetupOpts } from "../core/codemirror/cm";
import { userConfigAtom } from "../core/config/config";
import { darkTheme } from "../core/codemirror/theme/dark";
import { lightTheme } from "../core/codemirror/theme/light";
import { OverridingHotkeyProvider } from "../core/hotkeys/hotkeys";
import { store } from "../core/state/jotai";

// Partial config for storybook demo
const demoConfig: Partial<CodeMirrorSetupOpts> = {
  completionConfig: {
    activate_on_typing: false,
    signature_hint_on_typing: false,
    copilot: false,
    codeium_api_key: null,
  },
  hotkeys: new OverridingHotkeyProvider({}),
  showPlaceholder: false,
  enableAI: false,
  keymapConfig: { preset: "default" },
};

const meta: Meta = {
  title: "Theme",
  args: {},
};

export default meta;
type Story = StoryObj;

const CONTENT = `
# Example code to showcase theme differences
class ExampleClass:
    def __init__(self, value):
        self.value = value
        self.data = {}

    def get_value(self):
        return self.value

    @property
    def data_size(self):
        return len(self.data)

# Create instance and use methods/properties
example = ExampleClass(42)
result = example.get_value()
size = example.data_size
`.trim();

const READONLY_CONTENT = Array.from(
  { length: 80 },
  (_, index) => `value_${index + 1} = ${index + 1}`,
).join("\n");

const Editor = (opts: { extensions?: Extension[] }): React.ReactNode => {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) {
      return;
    }

    const view = new EditorView({
      state: EditorState.create({
        extensions: opts.extensions,
        doc: CONTENT,
      }),
      parent: element,
    });

    return () => view.destroy();
  }, [opts.extensions]);

  return <div className="cm" ref={ref} />;
};

export const ThemeComparison: Story = {
  render: () => (
    <div className="flex gap-4">
      <div className="w-1/2">
        <h3 className="mb-2 text-lg font-semibold">Light Theme</h3>
        <div className="overflow-hidden rounded border">
          <Editor
            extensions={[
              python(),
              lightTheme,
              ...basicBundle({
                ...demoConfig,
                theme: "light",
              } as CodeMirrorSetupOpts),
            ]}
          />
        </div>
      </div>
      <div className="w-1/2">
        <h3 className="mb-2 text-lg font-semibold">Dark Theme</h3>
        <div className="overflow-hidden rounded border">
          <Editor
            extensions={[
              python(),
              darkTheme,
              ...basicBundle({
                ...demoConfig,
                theme: "dark",
              } as CodeMirrorSetupOpts),
            ]}
          />
        </div>
      </div>
    </div>
  ),
};

const ReadonlyCodeThemeFixture = (): React.ReactNode => {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const previousConfig = store.get(userConfigAtom);
    store.set(userConfigAtom, {
      ...previousConfig,
      display: { ...previousConfig.display, theme },
    });

    return () => store.set(userConfigAtom, previousConfig);
  }, [theme]);

  return (
    <div className="max-w-3xl space-y-3" style={{ colorScheme: theme }}>
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">ReadonlyCode fixture</h3>
          <p className="text-sm text-muted-foreground">
            Select text, scroll, then switch themes to check that both remain.
          </p>
        </div>
        <div className="flex gap-2" role="group" aria-label="Theme">
          {(["light", "dark"] as const).map((nextTheme) => (
            <button
              aria-pressed={theme === nextTheme}
              className="rounded border px-3 py-1 text-sm"
              key={nextTheme}
              onClick={() => setTheme(nextTheme)}
              type="button"
            >
              {nextTheme}
            </button>
          ))}
        </div>
      </div>
      <div className="h-64 overflow-hidden rounded border">
        <ReadonlyCode
          className="h-full [&_.cm-editor]:h-full [&_.cm-scroller]:h-full [&_.cm-theme-none]:h-full"
          code={READONLY_CONTENT}
          showCopyCode={false}
          showHideCode={false}
        />
      </div>
    </div>
  );
};

export const ReadonlyCodeThemeReconfiguration: Story = {
  render: () => <ReadonlyCodeThemeFixture />,
};
