/* Copyright 2024 Marimo. All rights reserved. */
import React, { useState, useEffect } from "react";
import { SearchIcon } from "lucide-react";
import { Spinner } from "../icons/spinner";
import { cn } from "@/utils/cn";
import { useDebounce } from "@uidotdev/usehooks";
import useEvent from "react-use-event-hook";

interface SearchBarProps {
  hidden: boolean;
  value: string;
  handleSearch: (query: string) => void;
  onHide: () => void;
  reloading?: boolean;
}

export const SearchBar = ({
  hidden,
  value,
  handleSearch,
  onHide,
  reloading,
}: SearchBarProps) => {
  const [internalValue, setInternalValue] = useState(value);
  const debouncedSearch = useDebounce(internalValue, 500);
  const onSearch = useEvent(handleSearch);
  const ref = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    onSearch(debouncedSearch);
  }, [debouncedSearch, onSearch]);

  useEffect(() => {
    if (hidden) {
      setInternalValue("");
    } else {
      ref.current?.focus();
    }
  }, [hidden]);

  return (
    <div
      className={cn(
        "flex items-center space-x-2 h-8 px-2 border-b transition-all overflow-hidden duration-300 opacity-100",
        hidden && "h-0 border-none opacity-0",
      )}
    >
      <SearchIcon className="w-4 h-4 text-muted-foreground" />
      <input
        type="text"
        ref={ref}
        className="w-full h-full border-none bg-transparent focus:outline-none text-sm"
        value={internalValue}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            onHide();
          }
        }}
        onChange={(e) => setInternalValue(e.target.value)}
        placeholder="Search"
      />
      {reloading && <Spinner size="small" />}
    </div>
  );
};
