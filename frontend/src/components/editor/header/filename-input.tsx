/* Copyright 2024 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";

import { cn } from "../../../utils/cn";
import { sendListFiles } from "@/core/network/requests";
import { Paths } from "@/utils/paths";
import { useAsyncData } from "@/hooks/useAsyncData";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "../../ui/command";
import { FilePenIcon } from "lucide-react";
import { FILE_TYPE_ICONS, guessFileType } from "../file-tree/types";
import { Popover, PopoverContent } from "../../ui/popover";
import { PopoverAnchor } from "@radix-ui/react-popover";
import type { FileInfo } from "@/core/network/types";

import "./filename-input.css";
import { ErrorBoundary } from "../boundary/ErrorBoundary";
import { getFeatureFlag } from "@/core/config/feature-flag";

interface FilenameInputProps {
  resetOnBlur?: boolean;
  placeholderText?: string;
  initialValue?: string | null;
  className?: string;
  flexibleWidth?: boolean;
  onNameChange: (value: string) => void;
}

export const FilenameInput = ({
  resetOnBlur = false,
  placeholderText,
  initialValue = null,
  flexibleWidth = false,
  onNameChange,
  className,
}: FilenameInputProps): JSX.Element => {
  const [searchValue, setSearchValue] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<FileInfo[]>([]);
  const [focused, setFocused] = useState<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const skipReset = useRef<boolean>(false);

  useEffect(() => {
    setSearchValue(initialValue);
  }, [initialValue]);

  const onFocus = () => {
    setFocused(true);
  };

  const onBlur = (evt: React.FocusEvent<HTMLInputElement>) => {
    // If we are coming from a click event from inside the popover, don't blur
    if (evt.relatedTarget?.closest(".filename-input")) {
      return;
    }

    setFocused(false);
    if (resetOnBlur) {
      setSearchValue(initialValue);
    }
  };

  const dirname = Paths.dirname(searchValue || "");
  const basename = Paths.basename(searchValue || "");

  const filteredSuggestions = suggestions.filter((suggestion) =>
    Paths.basename(suggestion.path).startsWith(basename),
  );

  const { loading } = useAsyncData(async () => {
    if (!focused) {
      setSuggestions([]);
      return;
    }

    const data = await sendListFiles({ path: dirname });
    setSuggestions(data.files);
  }, [dirname, focused]);

  const suggestedNamed = getSuggestion(searchValue, suggestions, initialValue);

  const handleNameChange = () => {
    if (suggestedNamed) {
      // Don't reset the value
      skipReset.current = true;
      onNameChange(suggestedNamed);
      inputRef.current?.blur();
    }
  };

  const shouldShowList = suggestedNamed || filteredSuggestions.length > 0;
  const suggestionsList = shouldShowList && (
    <CommandList className="font-mono">
      {!loading && <CommandEmpty>No files</CommandEmpty>}

      {suggestedNamed && (
        <CommandItem
          key="_rename_"
          variant="success"
          className="py-2 px-3"
          onSelect={handleNameChange}
        >
          <FilePenIcon className="w-4 h-4 mr-2" />{" "}
          <span className="text-sm">
            {initialValue ? "Rename to: " : "Save as: "}
            <span className="font-medium text-sm">
              {Paths.basename(suggestedNamed)}
            </span>
          </span>
        </CommandItem>
      )}

      {filteredSuggestions.map((suggestion) => {
        const fileType = suggestion.isDirectory
          ? "directory"
          : guessFileType(suggestion.path);
        const Icon = FILE_TYPE_ICONS[fileType];

        const handleCommand = () => {
          if (suggestion.isDirectory) {
            setSearchValue(`${suggestion.path}/`);
          } else {
            setSearchValue(suggestion.path);
          }
        };

        return (
          <CommandItem
            key={suggestion.path}
            variant={suggestion.isDirectory ? "default" : "muted"}
            className="py-2 px-3"
            onSelect={handleCommand}
          >
            <Icon className="w-4 h-4 mr-2" /> {Paths.basename(suggestion.path)}
          </CommandItem>
        );
      })}
    </CommandList>
  );

  const size =
    Math.max(20, searchValue?.length || placeholderText?.length || 0) * 10;

  return (
    <ErrorBoundary>
      <Popover open={focused} modal={false}>
        <Command
          onFocus={onFocus}
          onBlur={onBlur}
          shouldFilter={false}
          id="filename-input"
          className="bg-transparent group filename-input"
        >
          <CommandList>
            <PopoverAnchor>
              <CommandInput
                data-testid="dir-completion-input"
                tabIndex={-1}
                rootClassName="border-none justify-center px-1"
                spellCheck="false"
                value={focused ? searchValue || "" : initialValue || ""}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    e.currentTarget.blur();
                  }
                }}
                icon={null}
                ref={inputRef}
                onValueChange={setSearchValue}
                placeholder={placeholderText}
                autoComplete="off"
                style={flexibleWidth ? { maxWidth: size } : undefined}
                className={cn(
                  className,
                  "w-full px-4 py-1 my-1 h-9 font-mono text-foreground/60",
                )}
              />
            </PopoverAnchor>

            <PopoverContent
              side="bottom"
              className={cn(
                "p-0 w-full min-w-80 max-w-80vw hidden",
                suggestionsList && "group-focus-within:block",
              )}
              portal={false}
            >
              {suggestionsList}
            </PopoverContent>
          </CommandList>
        </Command>
      </Popover>
    </ErrorBoundary>
  );
};

function getSuggestion(
  search: string | undefined | null,
  existing: FileInfo[],
  currentFilename: string | null,
): string | undefined {
  if (!search) {
    return;
  }
  if (search.endsWith("/")) {
    return;
  }

  // Matches allowed files in marimo/_utils/marimo_path.py
  const extensionsToLeave = getFeatureFlag("markdown")
    ? new Set(["py", "md", "markdown", "qmd"])
    : new Set(["py"]);

  if (extensionsToLeave.has(Paths.extension(search))) {
    // If ends with an allowed extension, leave as is
  } else if (search.endsWith(".")) {
    search = `${search}py`;
  } else if (search.endsWith(".p")) {
    search = `${search}y`;
  } else {
    search = `${search}.py`;
  }

  if (
    existing.some((s) => s.path === search || Paths.basename(s.path) === search)
  ) {
    return;
  }

  if (
    currentFilename &&
    (currentFilename === search || Paths.basename(currentFilename) === search)
  ) {
    return;
  }

  return search;
}
