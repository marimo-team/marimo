import type { Meta, StoryObj } from "@storybook/react";
import React, { useEffect, useRef } from "react";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { basicBundle, type CodeMirrorSetupOpts, type CellId } from "../core/codemirror/cm";
import { python } from "@codemirror/lang-python";
import { OverridingHotkeyProvider } from "../core/hotkeys/hotkeys";
import { darkTheme } from "../core/codemirror/theme/dark";
import { lightTheme } from "../core/codemirror/theme/light";
import type { MovementCallbacks } from "../core/cells/movement";
import type { CodeCallbacks } from "../core/cells/code";

// Partial config for storybook demo
const demoConfig: Partial<CodeMirrorSetupOpts> = {
  completionConfig: { activate_on_typing: false, copilot: false, codeium_api_key: null },
  hotkeys: new OverridingHotkeyProvider({}),
  cellId: "demo" as CellId,
  showPlaceholder: false,
  enableAI: false,
  cellMovementCallbacks: {
    moveToNextCell: () => {},
    onRun: () => {},
    deleteCell: () => {},
    createAbove: () => {},
    createBelow: () => {},
    moveUp: () => {},
    moveDown: () => {},
    focusEditor: () => {},
    focusNextCell: () => {},
    focusPrevCell: () => {},
    save: () => {},
    undo: () => {},
    redo: () => {},
    toggleMarkdown: () => {},
    toggleOutput: () => {},
  } as MovementCallbacks,
  cellCodeCallbacks: {
    updateCellCode: () => {},
    afterToggleMarkdown: () => {},
  } as CodeCallbacks,
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
    if (!ref.current) {
      return;
    }

    const view = new EditorView({
      state: EditorState.create({
        extensions: opts.extensions,
        doc: CONTENT,
      }),
      parent: ref.current,
    });

    return () => view.destroy();
  }, [ref.current]);

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
