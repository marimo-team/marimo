/* Copyright 2024 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuTrigger,
} from "../components/ui/context-menu";

const meta: Meta<typeof ContextMenu> = {
  title: "Components/ContextMenu",
  component: ContextMenu,
  parameters: {
    docs: {
      description: {
        component:
          "Context menu component that shows a custom menu by default. Use Shift + Right Click to access the browser's native context menu instead.",
      },
    },
  },
};
export default meta;

type Story = StoryObj<typeof ContextMenu>;

export const Default: Story = {
  render: () => (
    <ContextMenu>
      <ContextMenuTrigger className="block w-48 h-12 border rounded text-center leading-[3rem]">
        Right click for custom menu, Shift + Right click for browser menu
      </ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem>Custom Menu Item 1</ContextMenuItem>
        <ContextMenuItem>Custom Menu Item 2</ContextMenuItem>
        <ContextMenuItem>Custom Menu Item 3</ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  ),
};

export const WithLongContent: Story = {
  render: () => (
    <ContextMenu>
      <ContextMenuTrigger className="block w-96 h-32 border rounded p-4">
        <p>This is a longer content area that you can right-click on.</p>
        <p className="mt-2 text-sm text-muted-foreground">
          Right-click to show the custom menu, or use Shift + Right Click for
          the browser's default menu.
        </p>
      </ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuItem>View Details</ContextMenuItem>
        <ContextMenuItem>Share</ContextMenuItem>
        <ContextMenuItem variant="danger">Delete</ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  ),
};
