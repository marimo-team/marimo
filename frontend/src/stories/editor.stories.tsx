/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import type { Meta, StoryObj } from "@storybook/react";
import CodeMirror from "@uiw/react-codemirror";
import { useEffect, useRef } from "react";
import { CopilotConfig } from "@/core/codemirror/copilot/copilot-config";
import { copilotBundle } from "@/core/codemirror/copilot/extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { basicBundle, type CodeMirrorSetupOpts } from "../core/codemirror/cm";

const meta: Meta = {
  title: "Editor",
  args: {},
};

export default meta;
type Story = StoryObj;

const CONTENT = `
class Foo:
    def __init__(self):
        pass

# Some comment

# some other comment
def bar():
    pass


def foo():
    # another comment
    pass
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref.current]);

  return <div className="cm" ref={ref} />;
};

export const Primary: Story = {
  render: (args, ctx) => (
    <div className="Cell m-20 w-[60%] overflow-hidden">
      <Editor
        extensions={basicBundle({
          completionConfig: { activate_on_typing: false, copilot: false },
          theme: ctx.globals.theme,
          hotkeys: new OverridingHotkeyProvider({}),
        } as unknown as CodeMirrorSetupOpts)}
      />
    </div>
  ),
};

export const DefaultPython: Story = {
  render: () => (
    <div className="m-20 w-[60%] overflow-hidden">
      <CodeMirror
        extensions={[
          python(),
          copilotBundle({
            activate_on_typing: true,
            copilot: false,
            codeium_api_key: null,
          }),
        ]}
      />
      <CopilotConfig />
    </div>
  ),
};
