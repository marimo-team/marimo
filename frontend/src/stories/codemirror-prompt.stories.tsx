/* Copyright 2024 Marimo. All rights reserved. */
import ReactCodemirror, { basicSetup } from "@uiw/react-codemirror";
import { promptPlugin } from "../core/codemirror/prompt/prompt";
import { python } from "@codemirror/lang-python";
import type { Meta, StoryObj } from "@storybook/react";
import React from "react";

const CodeMirrorPrompt: React.FC = () => {
  return (
    <ReactCodemirror
      value={`
import marimo as mo
mo.App()
def add(a: int, b: int) -> int:
  return a + b

mo.ui.button(label="Click me")
  `}
      extensions={[
        basicSetup(),
        python(),
        promptPlugin(async (selection, code) => {
          return "def sub(a: int, b: int) -> int:\n  return a - b";
        }),
      ]}
    />
  );
};

const meta: Meta<typeof CodeMirrorPrompt> = {
  title: "CodeMirror/Prompt",
  component: CodeMirrorPrompt,
};

export default meta;
type Story = StoryObj<typeof CodeMirrorPrompt>;

export const Default: Story = {};
