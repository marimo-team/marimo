/* Copyright 2024 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/use-toast";
import { FormWrapper, type FormWrapperProps } from "@/plugins/impl/FormPlugin";
import { TooltipProvider } from "../components/ui/tooltip";

const meta: Meta<typeof FormWrapper> = {
  title: "FormWrapper",
  component: FormWrapper,
  args: {},
};

export default meta;
type Story = StoryObj<typeof FormWrapper>;

const props: FormWrapperProps<string> = {
  currentValue: "currentValue",
  newValue: "currentValue",
  setValue: (v) => {
    toast({
      title: "Form submitted",
    });
  },
  children: (
    <div className="space-y-4">
      <Input />
      <Checkbox />
      <Textarea />
      <RadioGroup>
        One
        <RadioGroupItem value="1" />
        Two
        <RadioGroupItem value="2" />
      </RadioGroup>
    </div>
  ),
  label: "My Form",
  bordered: true,
  loading: false,
  submitButtonLabel: "Submit",
  submitButtonTooltip: "Submit the form",
  submitButtonDisabled: false,
  clearOnSubmit: false,
  showClearButton: false,
  clearButtonLabel: "Clear",
  clearButtonTooltip: "Clear the form",
  shouldValidate: false,
  validate: async () => {
    return null;
  },
};

export const Primary: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper {...props} />
      </TooltipProvider>
    </div>
  ),
};

export const Loading: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper {...props} loading={true} />
      </TooltipProvider>
    </div>
  ),
};

export const Stale: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper
          {...props}
          currentValue="currentValue"
          newValue="newValue"
        />
      </TooltipProvider>
    </div>
  ),
};

export const WithCustomValues: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper
          {...props}
          submitButtonLabel="Go"
          submitButtonTooltip="Run!"
          clearButtonLabel="Reset"
          clearButtonTooltip="Reset the form"
          showClearButton={true}
          clearOnSubmit={true}
        />
      </TooltipProvider>
    </div>
  ),
};

export const Borderless: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper {...props} bordered={false} />
      </TooltipProvider>
    </div>
  ),
};

export const BorderlessAndStale: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper {...props} bordered={false} newValue="newValue" />
      </TooltipProvider>
    </div>
  ),
};

export const Validate: Story = {
  render: () => (
    <div className="p-20 max-w-4xl">
      <TooltipProvider>
        <FormWrapper
          {...props}
          shouldValidate={true}
          validate={async ({ value }) => {
            const random = Math.random();
            if (random < 0.8) {
              return `Failed to validate. Random number was ${random}`;
            }
            return null;
          }}
        />
      </TooltipProvider>
    </div>
  ),
};
