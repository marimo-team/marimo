/* Copyright 2024 Marimo. All rights reserved. */
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import { getCellNames, useCellActions } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import {
  DEFAULT_CELL_NAME,
  normalizeName,
  getValidName,
} from "@/core/cells/names";
import { useOnMount } from "@/hooks/useLifecycle";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import React, { useRef, useState } from "react";

interface Props {
  className?: string;
  value: string;
  onChange: (newName: string) => void;
  placeholder?: string;
}

export const NameCellInput: React.FC<Props> = ({
  value,
  onChange,
  placeholder,
}) => {
  const ref = useRef<HTMLInputElement>(null);
  const inputProps = useCellNameInput(value, onChange);

  // Custom onBlur without React's synthetic events
  // See https://github.com/facebook/react/issues/12363
  useOnMount(() => {
    const onBlur = inputProps.onBlur;
    const input = ref.current;
    if (!input) {
      return;
    }

    input.addEventListener("blur", onBlur);
    return () => {
      input.removeEventListener("blur", onBlur);
    };
  });

  return (
    <Input
      data-testid="cell-name-input"
      value={inputProps.value}
      onChange={inputProps.onChange}
      ref={ref}
      placeholder={placeholder}
      className="shadow-none! hover:shadow-none focus:shadow-none focus-visible:shadow-none"
      onKeyDown={Events.onEnter(Events.stopPropagation())}
    />
  );
};

export const NameCellContentEditable: React.FC<{
  cellId: CellId;
  value: string;
  className: string;
}> = ({ value, cellId, className }) => {
  const { updateCellName } = useCellActions();
  const inputProps = useCellNameInput(value, (newName) =>
    updateCellName({ cellId, name: newName }),
  );

  // If the name is the default, don't render the content editable
  if (value === DEFAULT_CELL_NAME) {
    return null;
  }

  return (
    <Tooltip content="Click to rename">
      <span
        className={cn(
          "outline-none border hover:border-cyan-500/40 focus:border-cyan-500/40",
          className,
        )}
        contentEditable={true}
        suppressContentEditableWarning={true}
        onChange={inputProps.onChange}
        onBlur={inputProps.onBlur}
        onKeyDown={Events.onEnter((e) => {
          if (e.target instanceof HTMLElement) {
            e.target.blur();
          }
        })}
      >
        {value}
      </span>
    </Tooltip>
  );
};

function useCellNameInput(value: string, onChange: (newName: string) => void) {
  const [internalValue, setInternalValue] = useState(value);

  const commit = (newValue: string) => {
    // No change
    if (newValue === value) {
      return;
    }

    // Empty
    if (!newValue || newValue === DEFAULT_CELL_NAME) {
      onChange(newValue);
      return;
    }

    // Get unique name
    const validName = getValidName(newValue, getCellNames());
    onChange(validName);
  };

  return {
    value: internalValue === DEFAULT_CELL_NAME ? "" : internalValue,
    onChange: (evt: React.ChangeEvent<HTMLInputElement>) => {
      const newValue = evt.target.value;
      const normalized = normalizeName(newValue);
      setInternalValue(normalized);
    },
    onBlur: (evt: Pick<Event, "target">) => {
      if (evt.target instanceof HTMLInputElement) {
        const newValue = evt.target.value;
        commit(normalizeName(newValue));
      } else if (evt.target instanceof HTMLSpanElement) {
        const newValue = evt.target.innerText.trim();
        commit(normalizeName(newValue));
      }
    },
  };
}
