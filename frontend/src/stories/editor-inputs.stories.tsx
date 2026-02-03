/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryFn } from "@storybook/react-vite";
import { PlayIcon } from "lucide-react";
import { useId } from "react";
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

const InputTemplateComponent = (args: React.ComponentProps<typeof Input>) => {
  const id = useId();
  return (
    <div className="m-4">
      <Input {...args} id={id} className="filename" />
    </div>
  );
};

const InputTemplate: StoryFn<typeof Input> = (args) => (
  <InputTemplateComponent {...args} />
);
export const InputStory = InputTemplate.bind({});
InputStory.args = {};
