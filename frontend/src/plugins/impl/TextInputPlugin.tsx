/* Copyright 2026 Marimo. All rights reserved. */

import { AtSignIcon, GlobeIcon, LockIcon } from "lucide-react";
import { type JSX, useRef, useState } from "react";
import { z } from "zod";
import {
  DebouncedInput,
  Input,
  OnBlurredInput,
} from "../../components/ui/input";
import { cn } from "../../utils/cn";
import type { IPlugin, IPluginProps, Setter } from "../types";
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
  debounce?: boolean | number;
  fullWidth: boolean;
  passwordHasValue?: boolean;
}

// Matches the masked dots.
const MASK_PLACEHOLDER = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022";

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
    debounce: z.optional(z.union([z.boolean(), z.number()])),
    passwordHasValue: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    // Force remount on cell re-run so useState resets cleanly
    const remountKey =
      props.data.kind === "password"
        ? props.host.parentElement?.getAttribute("random-id")
        : undefined;
    return (
      <TextComponent
        key={remountKey ?? undefined}
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
  const isPasswordWithValue =
    props.kind === "password" && props.passwordHasValue === true;

  // Before first edit: show masked placeholder, suppress value updates.
  // After first edit: get out of the way entirely — normal password field.
  const [hasInteracted, setHasInteracted] = useState(!isPasswordWithValue);
  const hasBeenEdited = useRef(false);

  const value = hasInteracted ? props.value : "";
  const placeholder = hasInteracted ? props.placeholder : MASK_PLACEHOLDER;
  const setValue: Setter<T> = hasInteracted
    ? props.setValue
    : (v) => {
        if (!hasBeenEdited.current) {
          return;
        }
        setHasInteracted(true);
        props.setValue(v);
      };

  const [valueOnBlur, setValueOnBlur] = useState(props.value);
  const valueToValidate = valueOnBlur == null ? value : valueOnBlur;
  const isValid = validate(props.kind, valueToValidate);

  const icon: Record<InputType, JSX.Element | null> = {
    text: null,
    password: <LockIcon size={16} />,
    email: <AtSignIcon size={16} />,
    url: <GlobeIcon size={16} />,
  };

  const endAdornment = props.maxLength ? (
    <span className="text-muted-foreground text-xs font-medium">
      {value.length}/{props.maxLength}
    </span>
  ) : null;

  // Only intercept input events before first interaction
  const maskHandlers = hasInteracted
    ? {}
    : {
        onInputCapture: () => {
          hasBeenEdited.current = true;
        },
      };

  let input: JSX.Element;

  if (props.debounce === true) {
    input = (
      <OnBlurredInput
        data-testid="marimo-plugin-text-input"
        type={props.kind}
        icon={icon[props.kind]}
        placeholder={placeholder}
        maxLength={props.maxLength}
        minLength={props.minLength}
        required={props.minLength != null && props.minLength > 0}
        disabled={props.disabled}
        className={cn({
          "border-destructive": !isValid,
          "w-full": props.fullWidth,
        })}
        endAdornment={endAdornment}
        value={value}
        onValueChange={setValue}
      />
    );
  } else if (typeof props.debounce === "number") {
    input = (
      <DebouncedInput
        data-testid="marimo-plugin-text-input"
        type={props.kind}
        icon={icon[props.kind]}
        placeholder={placeholder}
        maxLength={props.maxLength}
        minLength={props.minLength}
        required={props.minLength != null && props.minLength > 0}
        disabled={props.disabled}
        className={cn({
          "border-destructive": !isValid,
          "w-full": props.fullWidth,
        })}
        endAdornment={endAdornment}
        value={value}
        onValueChange={setValue}
        onBlur={(event) => setValueOnBlur(event.currentTarget.value)}
        delay={props.debounce}
      />
    );
  } else {
    input = (
      <Input
        data-testid="marimo-plugin-text-input"
        type={props.kind}
        icon={icon[props.kind]}
        placeholder={placeholder}
        maxLength={props.maxLength}
        minLength={props.minLength}
        required={props.minLength != null && props.minLength > 0}
        disabled={props.disabled}
        className={cn({
          "border-destructive": !isValid,
          "w-full": props.fullWidth,
        })}
        endAdornment={endAdornment}
        value={value}
        onInput={(event) => setValue(event.currentTarget.value)}
        onBlur={(event) => setValueOnBlur(event.currentTarget.value)}
      />
    );
  }

  return (
    <Labeled label={props.label} fullWidth={props.fullWidth}>
      <div {...maskHandlers}>{input}</div>
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
