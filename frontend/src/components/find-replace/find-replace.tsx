/* Copyright 2023 Marimo. All rights reserved. */
import {
  findReplaceAtom,
  openFindReplacePanel,
} from "@/core/codemirror/find-replace/state";
import { useAtom } from "jotai";
import React from "react";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import {
  findNext,
  findPrev,
  replaceAll,
  replaceNext,
} from "@/core/codemirror/find-replace/navigate";
import { Toggle } from "../ui/toggle";
import { Tooltip } from "../ui/tooltip";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CaseSensitiveIcon,
  RegexIcon,
  XIcon,
} from "lucide-react";
import { useHotkey } from "@/hooks/useHotkey";

export const FindReplace: React.FC = () => {
  const [isFocused, setIsFocused] = React.useState(false);
  const [state, dispatch] = useAtom(findReplaceAtom);
  useHotkey("cell.findAndReplace", () => {
    // if already open and focused, fallback to default behavior
    if (isFocused && state.isOpen) {
      return false;
    }

    return openFindReplacePanel();
  });

  if (!state.isOpen) {
    return null;
  }

  return (
    <div
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      className="fixed top-0 right-0 w-[500px] flex flex-col bg-[var(--sage-1)] p-4 z-50 mt-2 mr-3 rounded-md shadow-lg border gap-2"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          dispatch({ type: "setIsOpen", isOpen: false });
        }
      }}
    >
      <div className="absolute top-0 right-0">
        <Button
          onClick={() => dispatch({ type: "setIsOpen", isOpen: false })}
          size="xs"
          variant="text"
        >
          <XIcon className="w-4 h-4" />
        </Button>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex flex-col flex-2 gap-2 w-[55%]">
          <Input
            value={state.findText}
            autoFocus={true}
            className="mr-2 mb-0"
            placeholder="Find"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (e.shiftKey) {
                  findPrev();
                } else {
                  findNext();
                }
              }
            }}
            onChange={(e) => {
              dispatch({ type: "setFind", find: e.target.value });
            }}
          />
          <Input
            value={state.replaceText}
            placeholder="Replace"
            onChange={(e) => {
              dispatch({ type: "setReplace", replace: e.target.value });
            }}
          />
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-[2px]">
            <Tooltip content="Case Sensitive">
              <Toggle
                size="sm"
                pressed={state.caseSensitive}
                data-state={state.caseSensitive ? "on" : "off"}
                onPressedChange={(pressed) =>
                  dispatch({ type: "setCaseSensitive", caseSensitive: pressed })
                }
              >
                <CaseSensitiveIcon className="w-4 h-4" />
              </Toggle>
            </Tooltip>
            <Tooltip content="Use Regular Expression">
              <Toggle
                size="sm"
                pressed={state.regexp}
                data-state={state.regexp ? "on" : "off"}
                onPressedChange={(pressed) =>
                  dispatch({ type: "setRegex", regexp: pressed })
                }
              >
                <RegexIcon className="w-4 h-4" />
              </Toggle>
            </Tooltip>
          </div>
          <div className="flex items-center gap-[2px]">
            <Button
              size="xs"
              variant="outline"
              className="h-6 text-xs"
              onClick={() => replaceNext()}
              disabled={state.findText === "" || state.replaceText === ""}
            >
              Replace Next
            </Button>
            <Button
              size="xs"
              variant="outline"
              className="h-6 text-xs"
              onClick={() => replaceAll()}
              disabled={state.findText === "" || state.replaceText === ""}
            >
              Replace All
            </Button>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Tooltip content="Find Previous">
          <Button size="xs" variant="secondary" onClick={() => findPrev()}>
            <ArrowLeftIcon className="w-4 h-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Find Next">
          <Button size="xs" variant="secondary" onClick={() => findNext()}>
            <ArrowRightIcon className="w-4 h-4" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
};
