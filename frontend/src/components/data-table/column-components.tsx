/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "../ui/button";

export const FilterButtons = ({
  onApply,
  onClear,
  clearButtonDisabled,
}: {
  onApply: () => void;
  onClear: () => void;
  clearButtonDisabled?: boolean;
}) => {
  return (
    <div className="flex gap-2 px-2 justify-between">
      <Button variant="link" size="sm" onClick={onApply}>
        Apply
      </Button>
      <Button
        variant="linkDestructive"
        size="sm"
        className=""
        onClick={onClear}
        disabled={clearButtonDisabled}
      >
        Clear
      </Button>
    </div>
  );
};
