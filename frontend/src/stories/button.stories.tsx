/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/ui/button";
import { Mail, Trash2Icon, Loader2 } from "lucide-react";

export default {
  title: "Button",
  component: Button,
};

export const Default = {
  render: () => <Button>Button</Button>,
  name: "Default",
};

export const Success = {
  render: () => <Button variant="success">Button</Button>,
  name: "Success",
};

export const Warn = {
  render: () => <Button variant="warn">Button</Button>,
  name: "Warn",
};

export const Outline = {
  render: () => <Button variant="outline">Button</Button>,
  name: "Outline",
};

export const Destructive = {
  render: () => <Button variant="destructive">Button</Button>,
  name: "Destructive",
};

export const Action = {
  render: () => <Button variant="action">Button</Button>,
  name: "Action",
};

export const Secondary = {
  render: () => <Button variant="secondary">Button</Button>,
  name: "Secondary",
};

export const Ghost = {
  render: () => <Button variant="ghost">Ghost</Button>,
  name: "Ghost",
};

export const Link = {
  render: () => <Button variant="link">Link</Button>,
  name: "Link",
};

export const WithIcon = {
  render: () => (
    <Button>
      <Mail className="mr-2" />
      Button with icon
    </Button>
  ),

  name: "With Icon",
};

export const Loading = {
  render: () => (
    <Button disabled={true}>
      <Loader2 className="mr-2 animate-spin" />
      Please wait
    </Button>
  ),

  name: "Loading",
};

export const TrashIcon = {
  render: () => (
    <Button
      variant="ghost"
      size="icon"
      className="hover:bg-transparent hover:border-input"
    >
      <Trash2Icon size={14} className="text-destructive" />
    </Button>
  ),

  name: "Trash Icon",
};
