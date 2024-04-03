/* Copyright 2024 Marimo. All rights reserved. */
import { Checkbox } from "@/components/ui/checkbox";

export default {
  title: "Checkbox",
  component: Checkbox,
};

export const WithText = {
  render: () => (
    <div className="items-top flex space-x-2">
      <Checkbox id="terms1" />
      <div className="grid gap-1.5 leading-none">
        <label
          htmlFor="terms1"
          className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
        >
          Accept terms and conditions
        </label>
        <p className="text-sm text-muted-foreground">
          You agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </div>
  ),

  name: "With text",
};

export const Disabled = {
  render: () => (
    <div className="flex items-center space-x-2">
      <Checkbox id="terms2" disabled={true} />
      <label
        htmlFor="terms2"
        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
      >
        Accept terms and conditions
      </label>
    </div>
  ),

  name: "Disabled",
};
