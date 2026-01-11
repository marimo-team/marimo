/* Copyright 2026 Marimo. All rights reserved. */
import { useId } from "react";
import { Checkbox } from "@/components/ui/checkbox";

export default {
  title: "Checkbox",
  component: Checkbox,
};

export const WithText = {
  render: function Render() {
    const id = useId();
    return (
      <div className="items-top flex space-x-2">
        <Checkbox id={id} />
        <div className="grid gap-1.5 leading-none">
          <label
            htmlFor={id}
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Accept terms and conditions
          </label>
          <p className="text-sm text-muted-foreground">
            You agree to our Terms of Service and Privacy Policy.
          </p>
        </div>
      </div>
    );
  },

  name: "With text",
};

export const Disabled = {
  render: function Render() {
    const id = useId();
    return (
      <div className="flex items-center space-x-2">
        <Checkbox id={id} disabled={true} />
        <label
          htmlFor={id}
          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        >
          Accept terms and conditions
        </label>
      </div>
    );
  },

  name: "Disabled",
};
