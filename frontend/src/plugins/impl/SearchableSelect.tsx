/* Copyright 2024 Marimo. All rights reserved. */
import { useId, useMemo, useState } from "react";
import { Combobox, ComboboxItem } from "../../components/ui/combobox";
import { Labeled } from "./common/labeled";
import { cn } from "../../utils/cn";
import { multiselectFilterFn } from "./multiselectFilterFn";
import { Virtuoso } from "react-virtuoso";

interface SearchableSelectProps {
  options: string[];
  value: string | null;
  setValue: (value: string | null) => void;
  label: string | null;
  allowSelectNone: boolean;
  fullWidth: boolean;
}

const NONE_KEY = "__none__";

export const SearchableSelect = (props: SearchableSelectProps): JSX.Element => {
  const { options, value, setValue, label, allowSelectNone, fullWidth } = props;
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

  const handleValueChange = (newValue: string | null) => {
    if (newValue == null) {
      return;
    }

    if (newValue === NONE_KEY) {
      setValue(null);
    } else {
      setValue(newValue);
    }
  };

  const renderList = () => {
    const extraOptions = allowSelectNone ? (
      <ComboboxItem key={NONE_KEY} value={NONE_KEY}>
        --
      </ComboboxItem>
    ) : null;

    if (filteredOptions.length > 200) {
      return (
        <Virtuoso
          style={{ height: "200px" }}
          totalCount={filteredOptions.length}
          overscan={50}
          itemContent={(i: number) => {
            const option = filteredOptions[i];

            const comboboxItem = (
              <ComboboxItem key={option} value={option}>
                {option}
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
        displayValue={(option) => {
          if (option === NONE_KEY) {
            return "--";
          }
          return option;
        }}
        placeholder="Select..."
        multiple={false}
        className={cn("w-full", { "w-full": fullWidth })}
        value={value ?? NONE_KEY}
        onValueChange={handleValueChange}
        shouldFilter={false}
        search={searchQuery}
        onSearchChange={setSearchQuery}
        data-testid="marimo-plugin-searchable-dropdown"
      >
        {renderList()}
      </Combobox>
    </Labeled>
  );
};
