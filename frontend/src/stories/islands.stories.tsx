/* Copyright 2024 Marimo. All rights reserved. */
import { MarimoIsland } from "@/core/islands/main";

export default {
  title: "Marimo Islands",
  component: MarimoIsland,
};

// These don't actually start up since we run marimo in a WebWorker
// Which currently doesn't work in Storybook

export const Single = {
  render: () => <MarimoIsland code="2 + 2" />,

  name: "Single",
};

export const WithOutput = {
  render: () => <MarimoIsland code="2 + 2">Loading...</MarimoIsland>,

  name: "WithOutput",
};

export const NonReactive = {
  render: () => (
    <MarimoIsland code="2 + 2" reactive={false}>
      Loading...
    </MarimoIsland>
  ),

  name: "NonReactive",
};

export const Multiple = {
  render: () => (
    <div className="flex flex-col gap-4">
      <MarimoIsland code="x = 10" />
      <MarimoIsland code="x * 2" />
    </div>
  ),

  name: "Multiple",
};
