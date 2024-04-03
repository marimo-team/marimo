/* Copyright 2024 Marimo. All rights reserved. */
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";

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
  render: () => (
    <div className="grid w-full max-w-sm items-center gap-1.5">
      <Label htmlFor="email">Email</Label>
      <Input type="email" id="email" placeholder="Email" />
    </div>
  ),

  name: "With Label",
};

export const WithText = {
  render: () => (
    <div className="grid w-full max-w-sm items-center gap-1.5">
      <Label htmlFor="email-2">Email</Label>
      <Input type="email" id="email-2" placeholder="Email" />
      <p className="text-sm text-muted-foreground">Enter your email address.</p>
    </div>
  ),

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
