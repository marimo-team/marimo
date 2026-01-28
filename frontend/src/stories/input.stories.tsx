/* Copyright 2026 Marimo. All rights reserved. */

import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default {
  title: "Input",
  component: Input,
};

export const Default = {
  render: () => <Input type="email" className="w-1/4" placeholder="Email" />,
  name: "Default",
};

export const Disabled = {
  render: () => (
    <Input disabled={true} type="email" className="w-1/4" placeholder="Email" />
  ),
  name: "Disabled",
};

export const WithLabel = {
  render: function Render() {
    const id = useId();
    return (
      <div className="grid w-full max-w-sm items-center gap-1.5">
        <Label htmlFor={id}>Email</Label>
        <Input type="email" id={id} placeholder="Email" />
      </div>
    );
  },

  name: "With Label",
};

export const WithText = {
  render: function Render() {
    const id = useId();
    return (
      <div className="grid w-full max-w-sm items-center gap-1.5">
        <Label htmlFor={id}>Email</Label>
        <Input type="email" id={id} placeholder="Email" />
        <p className="text-sm text-muted-foreground">
          Enter your email address.
        </p>
      </div>
    );
  },

  name: "With Text",
};

export const WithButton = {
  render: () => (
    <div className="flex w-full max-w-sm items-center space-x-2">
      <Input type="email" placeholder="Email" />
      <Button type="submit">Subscribe</Button>
    </div>
  ),

  name: "With Button",
};
