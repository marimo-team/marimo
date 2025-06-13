/* Copyright 2024 Marimo. All rights reserved. */
import type { Meta, StoryFn } from "@storybook/react";
import { PlayIcon } from "lucide-react";
import { Button, Input } from "../components/editor/inputs/Inputs";

export default {
  title: "Editor Inputs",
  component: Button,
} as Meta;

const ButtonTemplate: StoryFn<typeof Button> = (args) => (
  <div className="m-4">
    <Button {...args}>
      <PlayIcon strokeWidth={1.5} size={16} />
    </Button>
  </div>
);
export const ButtonStory = ButtonTemplate.bind({});
ButtonStory.argTypes = {
  color: {
    type: {
      name: "enum",
      value: ["gray", "green", "red", "yellow", "hint-green"],
    },
  },
  size: {
    type: {
      name: "enum",
      value: ["small", "medium"],
    },
  },
  shape: {
    type: {
      name: "enum",
      value: ["circle", "rectangle"],
    },
  },
  onClick: { action: "clicked" },
};

const InputTemplate: StoryFn<typeof Input> = (args) => (
  <div className="m-4">
    <Input {...args} id="filename-input" className="filename" />
  </div>
);
export const InputStory = InputTemplate.bind({});
InputStory.args = {};
