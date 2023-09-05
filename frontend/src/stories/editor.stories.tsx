/* Copyright 2023 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react";
import { useEffect, useRef } from "react";
import { EditorState, Extension } from "@codemirror/state";
import { EditorView, basicSetup } from "codemirror";
import { setup } from "../core/codemirror/cm";
import { python } from "@codemirror/lang-python";

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
        extensions={setup({ activate_on_typing: false }, ctx.globals.theme)}
      />
    </div>
  ),
};

export const DefaultPython: Story = {
  render: () => (
    <div className="m-20 w-[60%] overflow-hidden">
      <Editor extensions={[basicSetup, python()]} />
    </div>
  ),
};
