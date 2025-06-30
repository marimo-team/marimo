/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { Meta, StoryObj } from "@storybook/react-vite";
import React, { useEffect, useRef } from "react";
import { basicBundle, type CodeMirrorSetupOpts } from "../core/codemirror/cm";
import { darkTheme } from "../core/codemirror/theme/dark";
import { lightTheme } from "../core/codemirror/theme/light";
import { OverridingHotkeyProvider } from "../core/hotkeys/hotkeys";

// Partial config for storybook demo
const demoConfig: Partial<CodeMirrorSetupOpts> = {
  completionConfig: {
    activate_on_typing: false,
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
