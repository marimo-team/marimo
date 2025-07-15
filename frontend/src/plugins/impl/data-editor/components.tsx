/* Copyright 2024 Marimo. All rights reserved. */

import { capitalize } from "lodash-es";
import { PencilIcon, PlusIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { DataType } from "@/core/kernel/messages";

interface RenameColumnSubProps {
  currentColumnName: string;
  onRename: (newName: string) => void;
  onCancel: () => void;
}

export const RenameColumnSub: React.FC<RenameColumnSubProps> = ({
  currentColumnName,
  onRename,
  onCancel,
}) => {
  const [inputValue, setInputValue] = useState("");

  const handleRename = () => {
    if (inputValue.trim()) {
      onRename(inputValue.trim());
      setInputValue(currentColumnName);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleRename();
    } else if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <PencilIcon className="mr-2 h-3.5 w-3.5" />
        Rename column
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent className="w-64 p-4">
          <div className="space-y-3">
            <div>
              <Label htmlFor="rename-input">Column name</Label>
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                placeholder="Enter new column name"
                className="mt-1"
                onKeyDown={handleKeyDown}
              />
            </div>
            <Button
              onClick={handleRename}
              disabled={!inputValue.trim()}
              size="sm"
              className="w-full"
            >
              Rename
            </Button>
          </div>
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
};

interface AddColumnSubProps {
  direction: "left" | "right";
  onAdd: (columnName: string, dataType: DataType) => void;
  onCancel: () => void;
}

export const AddColumnSub: React.FC<AddColumnSubProps> = ({
  direction,
  onAdd,
  onCancel,
}) => {
  const [columnName, setColumnName] = useState("");
  const [dataType, setDataType] = useState<DataType>("string");

  const supportedDataTypes: DataType[] = [
    "string",
    "number",
    "boolean",
    "datetime",
  ];

  const handleAdd = () => {
    if (columnName.trim()) {
      onAdd(columnName.trim(), dataType);
      setColumnName("");
      setDataType("string"); // reset
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleAdd();
    } else if (e.key === "Escape") {
      onCancel();
    }
  };

  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <PlusIcon className="mr-2 h-3.5 w-3.5" />
        Add column to the {direction}
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent className="w-64 p-4">
          <div className="space-y-3">
            <div>
              <Label htmlFor={`add-column-input-${direction}`}>
                Column name
              </Label>
              <Input
                id={`add-column-input-${direction}`}
                value={columnName}
                onChange={(e) => setColumnName(e.target.value)}
                placeholder="Enter column name"
                className="mt-1"
                onKeyDown={handleKeyDown}
              />
            </div>
            <div>
              <Label htmlFor={`add-column-type-${direction}`}>Data type</Label>
              <Select
                value={dataType}
                onValueChange={(value) => setDataType(value as DataType)}
              >
                <SelectTrigger
                  id={`add-column-type-${direction}`}
                  className="mt-1"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {supportedDataTypes.map((type) => (
                    <SelectItem key={type} value={type}>
                      {capitalize(type)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleAdd}
              disabled={!columnName.trim()}
              size="sm"
              className="w-full"
            >
              Add
            </Button>
          </div>
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
};
