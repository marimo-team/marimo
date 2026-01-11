/* Copyright 2026 Marimo. All rights reserved. */

import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export default {
  title: "Textarea",
  component: Textarea,
};

export const Default = {
  render: () => <Textarea placeholder="Type your message here." />,
  name: "Default",
};

export const Disabled = {
  render: () => (
    <Textarea placeholder="Type your message here." disabled={true} />
  ),
  name: "Disabled",
};

export const WithLabel = {
  render: function Render() {
    const id = useId();
    return (
      <div className="grid w-full gap-1.5">
        <Label htmlFor={id}>Your message</Label>
        <Textarea placeholder="Type your message here." id={id} />
      </div>
    );
  },

  name: "With Label",
};

export const WithText = {
  render: function Render() {
    const id = useId();
    return (
      <div className="grid w-full gap-1.5">
        <Label htmlFor={id}>Your Message</Label>
        <Textarea placeholder="Type your message here." id={id} />
        <p className="text-sm text-muted-foreground">
          Your message will be copied to the support team.
        </p>
      </div>
    );
  },

  name: "With Text",
};

export const WithButton = {
  render: () => (
    <div className="grid w-full gap-2">
      <Textarea placeholder="Type your message here." />
      <Button>Send message</Button>
    </div>
  ),

  name: "With Button",
};
