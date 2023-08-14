/* Copyright 2023 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react";
import { Cell, CellProps } from "../editor/Cell";
import { TooltipProvider } from "../components/ui/tooltip";
import { CellId } from "../core/model/ids";

const meta: Meta<typeof Cell> = {
  component: Cell,
  args: {},
};

export default meta;
type Story = StoryObj<typeof Cell>;

const props: CellProps = {
  theme: "light",
  showPlaceholder: false,
  cellId: "1" as CellId,
  initialContents: "import marimo as mo",
  output: null,
  consoleOutputs: [],
  status: "idle",
  edited: false,
  interrupted: false,
  errored: false,
  updateCellCode: console.log,
  prepareCellForRun: console.log,
  registerRunStart: console.log,
  runElapsedTimeMs: 10,
  serializedEditorState: null,
  editing: true,
  appClosed: false,
  showDeleteButton: true,
  allowFocus: false,
  createNewCell: console.log,
  deleteCell: console.log,
  focusCell: console.log,
  moveCell: console.log,
  moveToNextCell: console.log,
  userConfig: {
    completion: {
      activate_on_typing: true,
    },
    save: {
      autosave: "off",
      autosave_delay: 1000,
    },
  },
};

export const Primary: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <Cell {...props} />
      </TooltipProvider>
    </div>
  ),
};

export const WithOutput: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <Cell
          {...props}
          runElapsedTimeMs={20}
          output={{
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: "1686863788",
          }}
        />
      </TooltipProvider>
    </div>
  ),
};

export const StaleOutput: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <Cell
          {...props}
          runElapsedTimeMs={20}
          edited={true}
          output={{
            channel: "output",
            data: "<span class='markdown'><h1>Layout</h1>\n<p><code>marimo</code> provides functions to help you lay out your output, such as\nin rows and columns, accordions, tabs, and callouts. This tutorial\nshows some examples.</p></span>",
            mimetype: "text/html",
            timestamp: "1686863788",
          }}
        />
      </TooltipProvider>
    </div>
  ),
};
