/* Copyright 2023 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "../types";
import { NativeSelect } from "../../components/ui/native-select";
import { Labeled } from "./common/labeled";

interface Data {
  label: string | null;
  options: string[];
  allowSelectNone: boolean;
}

export class DropdownPlugin implements IPlugin<string[], Data> {
  tagName = "marimo-dropdown";

  validator = z.object({
    initialValue: z.array(z.string()),
    label: z.string().nullable(),
    options: z.array(z.string()),
    allowSelectNone: z.boolean(),
  });

  render(props: IPluginProps<string[], Data>): JSX.Element {
    return (
      <Dropdown {...props.data} value={props.value} setValue={props.setValue} />
    );
  }
}

type T = string[];

/**
 * Arguments for a dropdown menu
 *
 * @param options - text labels for each dropdown option
 * @param allowSelectNone - whether to have a null option
 * @param label - an optional label for the dropdown
 * @param value - an array of options that is selected by default
 * @param setValue - selects a radio option
 */
interface DropdownProps extends Data {
  value: T;
  setValue: (value: T) => void;
}

const EMPTY_VALUE = "--";

const Dropdown = (props: DropdownProps): JSX.Element => {
  const { label, options, value, setValue, allowSelectNone } = props;

  const id = useId();

  const defaultValue = allowSelectNone ? EMPTY_VALUE : options[0];
  const singleValue = value.length === 0 ? defaultValue : value[0];

  return (
    <Labeled label={label} id={id}>
      <NativeSelect
        onChange={(e) => {
          const newValue = e.target.value;
          if (newValue === EMPTY_VALUE) {
            setValue([]);
          } else {
            setValue([newValue]);
          }
        }}
        value={singleValue}
        id={id}
      >
        {allowSelectNone ? (
          <option value={EMPTY_VALUE} selected={value.length === 0}>
            --
          </option>
        ) : null}
        {options.map((option) => (
          <option value={option} selected={value.includes(option)} key={option}>
            {option}
          </option>
        ))}
      </NativeSelect>
    </Labeled>
  );
};
