import { useId, useMemo, useState } from "react";
import { Combobox, ComboboxItem } from "../../components/ui/combobox";
import { Labeled } from "./common/labeled";
import { cn } from "../../utils/cn";
import { exportedForTesting } from "./MultiselectPlugin";

const { multiselectFilterFn } = exportedForTesting;

interface SearchableSelectProps {
  options: string[];
  value: string[];
  setValue: (value: string[]) => void;
  label: string | null;
  allowSelectNone: boolean;
  fullWidth: boolean;
}

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

  const handleValueChange = (newValues: string[] | null) => {
    if (!newValues || newValues.length === 0) {
      setValue([]);
      return;
    }
    // Only take the last selected value for single selection
    setValue([newValues[newValues.length - 1]]);
  };

  return (
    <Labeled label={label} id={id} fullWidth={fullWidth}>
      <Combobox<string>
        displayValue={(option) => option}
        placeholder="Select..."
        multiple={false}
        className={cn("w-full", { "w-full": fullWidth })}
        value={value[0] ?? null}
        onValueChange={(val) => handleValueChange(val ? [val] : [])}
        shouldFilter={false}
        search={searchQuery}
        onSearchChange={setSearchQuery}
        data-testid="marimo-plugin-searchable-dropdown"
      >
        {allowSelectNone && <ComboboxItem value="--">--</ComboboxItem>}
        {filteredOptions.map((option) => (
          <ComboboxItem key={option} value={option}>
            {option}
          </ComboboxItem>
        ))}
      </Combobox>
    </Labeled>
  );
};
