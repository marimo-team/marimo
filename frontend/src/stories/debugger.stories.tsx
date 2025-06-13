/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta, StoryFn } from "@storybook/react";
import { useState } from "react";
import { Debugger } from "@/components/debugger/debugger-code";

const meta: Meta<typeof Debugger> = {
  title: "Debugger",
  component: Debugger,
  args: {},
};

export default meta;

const Template: StoryFn<typeof Debugger> = (args) => {
  const [code, setCode] = useState([args.code]);
  return (
    <div className="bg-background">
      <Debugger
        code={code.join("\n")}
        onSubmit={(nextCode) => {
          setCode([...code, nextCode]);
          args.onSubmit(nextCode);
        }}
      />
    </div>
  );
};

export const Default = Template.bind({});
Default.args = {
  code: "print('Hello, world!')",
  onSubmit: (code) => console.log(code),
};
