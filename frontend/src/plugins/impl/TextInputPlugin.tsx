/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { Input } from "../../components/ui/input";
import { cn } from "../../utils/cn";
import { AtSignIcon, GlobeIcon, LockIcon } from "lucide-react";
import { useState } from "react";
import { Labeled } from "./common/labeled";

type T = string;

type InputType = "text" | "password" | "email" | "url";

interface Data {
  placeholder: string;
  label: string | null;
  kind: InputType;
  maxLength?: number;
  minLength?: number;
  disabled?: boolean;
  fullWidth: boolean;
}

export class TextInputPlugin implements IPlugin<T, Data> {
  tagName = "marimo-text";

  validator = z.object({
    initialValue: z.string(),
    placeholder: z.string(),
    label: z.string().nullable(),
    kind: z.enum(["text", "password", "email", "url"]).default("text"),
    maxLength: z.number().optional(),
    minLength: z.number().optional(),
    fullWidth: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <TextComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface TextComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const TextComponent = (props: TextComponentProps) => {
  const [valueOnBlur, setValueOnBlur] = useState(props.value);

  const valueToValidate = valueOnBlur == null ? props.value : valueOnBlur;
  const isValid = validate(props.kind, valueToValidate);

  const icon: Record<InputType, JSX.Element | null> = {
    text: null,
    password: <LockIcon size={16} />,
    email: <AtSignIcon size={16} />,
    url: <GlobeIcon size={16} />,
  };

  const endAdornment = props.maxLength ? (
    <span className="text-muted-foreground text-xs font-medium">
      {props.value.length}/{props.maxLength}
    </span>
  ) : null;

  return (
    <Labeled label={props.label} fullWidth={props.fullWidth}>
      <Input
        data-testid="marimo-plugin-text-input"
        type={props.kind}
        icon={icon[props.kind]}
        placeholder={props.placeholder}
        maxLength={props.maxLength}
        minLength={props.minLength}
        required={props.minLength != null && props.minLength > 0}
        disabled={props.disabled}
        className={cn({
          "border-destructive": !isValid,
          "w-full": props.fullWidth,
        })}
        endAdornment={endAdornment}
        value={props.value}
        onInput={(event) => props.setValue(event.currentTarget.value)}
        onBlur={(event) => setValueOnBlur(event.currentTarget.value)}
      />
    </Labeled>
  );
};

function validate(kind: InputType, value: string): boolean {
  // We don't validate required-ness to empty is valid
  if (!value) {
    return true;
  }

  // We only validate email and url types
  switch (kind) {
    case "email":
      return z.string().email().safeParse(value).success;
    case "url":
      return z.string().url().safeParse(value).success;
    default:
      return true;
  }
}
