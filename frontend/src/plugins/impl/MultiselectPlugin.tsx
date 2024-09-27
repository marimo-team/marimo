/* Copyright 2024 Marimo. All rights reserved. */
import { useId, useMemo, useState } from "react";
import { z } from "zod";

import type { IPlugin, IPluginProps, Setter } from "../types";
import { Combobox, ComboboxItem } from "../../components/ui/combobox";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";
import { Virtuoso } from "react-virtuoso";
import { CommandSeparator } from "../../components/ui/command";

interface Data {
  label: string | null;
  options: string[];
  fullWidth: boolean;
  maxSelections?: number | undefined;
}

type T = string[];

export class MultiselectPlugin implements IPlugin<T, Data> {
  tagName = "marimo-multiselect";

  validator = z.object({
    initialValue: z.array(z.string()),
    label: z.string().nullable(),
    options: z.array(z.string()),
    fullWidth: z.boolean().default(false),
    maxSelections: z.number().optional(),
  });

  render(props: IPluginProps<string[], Data>): JSX.Element {
    return (
      <Multiselect
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

/**
 * Arguments for a multi select
 *
 * @param options - text labels for each select option
 * @param label - an optional label for the select
 * @param value - an array of options that are selected
 * @param setValue - set multi select value
 */
interface MultiselectProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const SELECT_ALL_KEY = "__select_all__";
const DESELECT_ALL_KEY = "__deselect_all__";

const Multiselect = ({
  options,
  label,
  value,
  setValue,
  fullWidth,
  maxSelections,
}: MultiselectProps): JSX.Element => {
  const id = useId();
  const [searchQuery, setSearchQuery] = useState<string>("");

  const filteredOptions = useMemo(() => {
    if (!searchQuery) {
      return options;
    }
    return options.filter(
      (option) => multiselectFilterFn(option, searchQuery) === 1,
    );
  }, [options, searchQuery]);

  const handleValueChange = (newValues: string[] | null) => {
    if (!newValues) {
      setValue([]);
      return;
    }
    if (maxSelections != null && newValues.length > maxSelections) {
      return;
    }
    // Remove select all and deselect all from the new values
    newValues = newValues.filter(
      (value) => value !== SELECT_ALL_KEY && value !== DESELECT_ALL_KEY,
    );
    setValue(newValues);
  };

  const handleSelectAll = () => {
    setValue(options);
  };

  const handleDeselectAll = () => {
    setValue([]);
  };

  const shouldShowSelectAll =
    options.length > 0 && value.length < options.length;
  const shouldShowDeselectAll = options.length > 0 && value.length > 0;

  // Only show when more than 2 options
  const extraOptions = options.length > 2 && (
    <>
      <ComboboxItem
        key={SELECT_ALL_KEY}
        value={SELECT_ALL_KEY}
        onSelect={handleSelectAll}
        disabled={!shouldShowSelectAll}
      >
        Select all
      </ComboboxItem>
      <ComboboxItem
        key={DESELECT_ALL_KEY}
        value={DESELECT_ALL_KEY}
        onSelect={handleDeselectAll}
        disabled={!shouldShowDeselectAll}
      >
        Deselect all
      </ComboboxItem>
      <CommandSeparator />
    </>
  );

  const renderList = () => {
    // List virtualization
    if (filteredOptions.length > 200) {
      return (
        <Virtuoso
          style={{ height: "200px" }}
          totalCount={filteredOptions.length}
          overscan={50}
          itemContent={(i: number) => {
            const comboboxItem = (
              <ComboboxItem key={filteredOptions[i]} value={filteredOptions[i]}>
                {filteredOptions[i]}
              </ComboboxItem>
            );

            if (i === 0) {
              return (
                <>
                  {extraOptions}
                  {comboboxItem}
                </>
              );
            }

            return comboboxItem;
          }}
        />
      );
    }

    const list = filteredOptions.map((option) => (
      <ComboboxItem key={option} value={option}>
        {option}
      </ComboboxItem>
    ));

    return (
      <>
        {extraOptions}
        {list}
      </>
    );
  };

  return (
    <Labeled label={label} id={id} fullWidth={fullWidth}>
      <Combobox<string>
        displayValue={(option) => option}
        placeholder="Select..."
        multiple={true}
        className={cn({
          "w-full": fullWidth,
        })}
        value={value}
        onValueChange={handleValueChange}
        shouldFilter={false}
        search={searchQuery}
        onSearchChange={setSearchQuery}
      >
        {renderList()}
      </Combobox>
    </Labeled>
  );
};

/**
 * We override the default filter function which focuses on sorting by relevance with a fuzzy-match,
 * instead of filtering out.
 * The default filter function is `command-score`.
 *
 * Our filter function only matches if all words in the value are present in the option.
 * This is more strict than the default, but more lenient than an exact match.
 *
 * Examples:
 * - "foo bar" matches "foo bar"
 * - "bar foo" matches "foo bar"
 * - "foob" does not matches "foo bar"
 */
function multiselectFilterFn(option: string, value: string): number {
  const words = value.split(/\s+/);
  const match = words.every((word) =>
    option.toLowerCase().includes(word.toLowerCase()),
  );
  return match ? 1 : 0;
}

export const exportedForTesting = {
  multiselectFilterFn,
};
