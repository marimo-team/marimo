/* Copyright 2024 Marimo. All rights reserved. */
import {
  createRef,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from "react";

import { Input } from "./inputs/Inputs";
import { Logger } from "../../utils/Logger";
import { Functions } from "../../utils/functions";
import { cn } from "../../utils/cn";
import { sendListFiles } from "@/core/network/requests";
import { Paths } from "@/utils/paths";
import { useAsyncData } from "@/hooks/useAsyncData";

export interface DirCompletionInputHandle {
  suggestions: string[];
}

interface DirCompletionInputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  flexibleWidth?: boolean;
  resetOnBlur?: boolean;
  placeholderText?: string;
  initialValue?: string | null;
  onFocusCallback?: () => void;
  onBlurCallback?: () => void;
  onChangeCallback?: (value: string) => void;
  handle?: React.RefObject<DirCompletionInputHandle>;
}

export const DirCompletionInput = ({
  flexibleWidth = false,
  resetOnBlur = false,
  placeholderText = "",
  initialValue = null,
  onFocusCallback = Functions.NOOP,
  onBlurCallback = Functions.NOOP,
  onChangeCallback = Functions.NOOP,
  handle = createRef(),
  ...rest
}: DirCompletionInputProps): JSX.Element => {
  const [value, setValue] = useState(initialValue);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [activeSuggestion, setActiveSuggestion] = useState<number | null>(null);
  const [focused, setFocused] = useState<boolean>(false);

  useImperativeHandle(handle, () => ({
    get suggestions() {
      return suggestions;
    },
  }));
  const ref = useRef<HTMLInputElement>(null);
  const activeSuggestionRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    setValue(initialValue);
  }, [initialValue]);

  function onFocus(e: React.FocusEvent<HTMLInputElement>) {
    setFocused(true);
    onFocusCallback();
  }

  async function onBlur(e: React.FocusEvent<HTMLInputElement>) {
    // focus should be removed before value is reset, to avoid a race
    // condition in which suggestions are fetched when not needed
    setFocused(false);
    if (resetOnBlur) {
      e.preventDefault();
      setValue(initialValue);
    }
    onBlurCallback();
  }

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    setValue(e.target.value);
    onChangeCallback(e.target.value);
  }

  const dirname = Paths.dirname(value || "");
  const basename = Paths.basename(value || "");
  const filteredSuggestions = suggestions.filter((suggestion) =>
    suggestion.startsWith(basename),
  );

  useAsyncData(async () => {
    if (!focused) {
      setActiveSuggestion(null);
      setSuggestions([]);
      return;
    }

    const data = await sendListFiles({ path: dirname });
    // Only set suggestions if this token has not been invalidated
    setActiveSuggestion(null);
    const relativePaths = data.files.map((path) =>
      path.path.slice(data.root.length + 1),
    );
    setSuggestions(relativePaths);
  }, [dirname, focused]);

  function chooseSuggestion(index: number) {
    const prefix = value === null ? "" : value;
    const completion = suggestions[index].slice(basename.length);
    setValue(`${prefix + completion}/`);
    if (ref.current != null) {
      ref.current.focus();
    }
  }

  function handleSuggestionMouseDown(
    index: number,
    e: React.MouseEvent<HTMLLIElement>,
  ) {
    e.preventDefault();
    if (e.button === 0 && !suggestions[index].endsWith(".py")) {
      chooseSuggestion(index);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    switch (e.key) {
      case "Down":
      case "ArrowDown":
        setActiveSuggestion((i) =>
          i == null ? 0 : (i + 1) % suggestions.length,
        );
        e.preventDefault();
        break;
      case "Up":
      case "ArrowUp":
        setActiveSuggestion((i) =>
          i === null || i === 0 ? suggestions.length - 1 : i - 1,
        );
        e.preventDefault();
        break;
      case "Enter":
      case "ArrowRight":
        if (activeSuggestion === null) {
          break;
        }
        e.preventDefault();
        e.stopPropagation();
        if (!suggestions[activeSuggestion].endsWith(".py")) {
          chooseSuggestion(activeSuggestion);
        }
        break;
      case "Esc":
      case "Escape":
        if (ref.current !== null) {
          ref.current.blur();
        }
        e.preventDefault();
        break;
      default:
        break;
    }
  }

  useEffect(() => {
    if (activeSuggestion !== null && activeSuggestionRef.current != null) {
      const elem = activeSuggestionRef.current;
      const parent = elem.parentElement;
      if (parent === null) {
        Logger.error("Expected elem to have parent; elem:", elem);
      } else {
        const scrollOffset = parent.scrollTop;
        const visibleRange = [scrollOffset, scrollOffset + parent.offsetHeight];
        if (elem.offsetTop < visibleRange[0]) {
          activeSuggestionRef.current.scrollIntoView(/* alignToTop = */ true);
        } else if (elem.offsetTop + elem.offsetHeight > visibleRange[1]) {
          activeSuggestionRef.current.scrollIntoView(/* alignToTop = */ false);
        }
      }
    }
  }, [activeSuggestion]);

  const suggestionsList =
    filteredSuggestions.length === 0 || ref.current == null ? null : (
      <ul
        className="autocomplete-list"
        style={{
          maxWidth: ref.current.offsetWidth,
          width: ref.current.offsetWidth,
        }}
      >
        {filteredSuggestions.map((suggestion, index) => {
          const isFile = suggestion.endsWith(".py");
          const icon = isFile ? "📄" : "📁 ";
          const isActive = activeSuggestion === index;
          return (
            <li
              key={suggestion}
              className={cn({
                file: isFile,
                directory: !isFile,
                "active-suggestion": isActive,
              })}
              onMouseDown={(e) => handleSuggestionMouseDown(index, e)}
              ref={isActive ? activeSuggestionRef : null}
            >
              {icon} {suggestion}
            </li>
          );
        })}
      </ul>
    );

  let size: number | undefined;
  if (flexibleWidth) {
    size = Math.min(
      60,
      Math.max(placeholderText.length, value === null ? 0 : value.length),
    );
  }

  const displayValue =
    !focused && placeholderText !== ""
      ? placeholderText
      : value === null
        ? ""
        : value;
  return (
    <div className="DirCompletionInput">
      <Input
        type="text"
        spellCheck="false"
        value={displayValue}
        style={{ width: "unset" }}
        autoComplete="off"
        ref={ref}
        size={size}
        onFocus={onFocus}
        onChange={handleChange}
        onBlur={onBlur}
        onKeyDown={onKeyDown}
        {...rest}
      />
      {suggestionsList}
    </div>
  );
};
