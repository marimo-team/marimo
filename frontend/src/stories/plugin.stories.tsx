/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */
import type { Meta, StoryObj } from "@storybook/react";
import { UI_PLUGINS } from "../plugins/plugins";
import { useState } from "react";

const meta: Meta = {
  title: "Plugin",
  args: {},
};

export default meta;

const plugins = UI_PLUGINS;

export const Plugin: StoryObj = {
  render: () => {
    const [value, setValue] = useState(undefined);
    const selectedPlugin = plugins.find(
      (p) => p.tagName === "marimo-dataframe"
    );

    if (!selectedPlugin) {
      return <div>Plugin not found</div>;
    }

    return selectedPlugin.render({
      host: document.body,
      data: {
        label: "Transforms",
        initialValue: {},
      },
      value: value,
      setValue: setValue,
    });
  },
};
