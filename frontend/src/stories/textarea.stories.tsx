/* Copyright 2024 Marimo. All rights reserved. */
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";

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
  render: () => (
    <div className="grid w-full gap-1.5">
      <Label htmlFor="message">Your message</Label>
      <Textarea placeholder="Type your message here." id="message" />
    </div>
  ),

  name: "With Label",
};

export const WithText = {
  render: () => (
    <div className="grid w-full gap-1.5">
      <Label htmlFor="message-2">Your Message</Label>
      <Textarea placeholder="Type your message here." id="message-2" />
      <p className="text-sm text-muted-foreground">
        Your message will be copied to the support team.
      </p>
    </div>
  ),

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
