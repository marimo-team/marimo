/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { FocusScope } from "@react-aria/focus";
import { useAtom, useAtomValue } from "jotai";
import {
  ArrowLeftIcon,
  ArrowRightIcon,
  CaseSensitiveIcon,
  RegexIcon,
  WholeWordIcon,
  XIcon,
} from "lucide-react";
import type React from "react";
import { useEffect, useRef, useState } from "react";
import {
  findNext,
  findPrev,
  getMatches,
  replaceAll,
  replaceNext,
} from "@/core/codemirror/find-replace/navigate";
import {
  clearGlobalSearchQuery,
  setGlobalSearchQuery,
} from "@/core/codemirror/find-replace/search-highlight";
import {
  findReplaceAtom,
  openFindReplacePanel,
} from "@/core/codemirror/find-replace/state";
import { hotkeysAtom } from "@/core/config/config";
import { useHotkey } from "@/hooks/useHotkey";
import { UndoButton } from "../buttons/undo-button";
import { KeyboardHotkeys } from "../shortcuts/renderShortcut";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Toggle } from "../ui/toggle";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";

export const FindReplace: React.FC = () => {
  const [isFocused, setIsFocused] = useState(false);
  const [state, dispatch] = useAtom(findReplaceAtom);
  const [matches, setMatches] = useState<{
    count: number;
    position: Map<EditorView, Map<string, number>>;
  }>();
  const findInputRef = useRef<HTMLInputElement>(null);
  const hotkeys = useAtomValue(hotkeysAtom);

  useHotkey("cell.findAndReplace", () => {
    // if already open and focused, fallback to default behavior
    if (isFocused && state.isOpen) {
      return false;
    }

    return openFindReplacePanel();
  });

  const resetMatches = () => {
    const matches = getMatches();
    // False count means an invalid regex
    setMatches(matches === false ? undefined : matches);
  };

  useEffect(() => {
    if (state.isOpen && findInputRef.current) {
      findInputRef.current.focus(); // Focus the input
      findInputRef.current.select(); // Select all text in the input
    }
  }, [state.isOpen]); // Depend on isOpen to trigger when the panel opens

  useEffect(() => {
    if (!state.isOpen) {
      clearGlobalSearchQuery();
      return;
    }

    if (state.findText === "") {
      setMatches(undefined);
      clearGlobalSearchQuery();
      return;
    }

    resetMatches();
    setGlobalSearchQuery();
  }, [
    // Re-search when any of these change
    state.findText,
    state.isOpen,
    state.caseSensitive,
    state.regexp,
    state.wholeWord,
  ]);

  if (!state.isOpen) {
    return null;
  }

  const selection = state.currentView;
  const currentMatch =
    selection && matches
      ? matches.position
          .get(selection.view)
          ?.get(`${selection.range.from}:${selection.range.to}`)
      : undefined;

  return (
    <FocusScope restoreFocus={true} autoFocus={true}>
      <div
        onFocus={() => setIsFocused(true)}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
        }}
        onBlur={() => setIsFocused(false)}
        className="fixed top-0 right-0 w-[500px] flex flex-col bg-[var(--sage-1)] p-4 z-50 mt-2 mr-3 rounded-md shadow-lg border gap-2 print:hidden"
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            dispatch({ type: "setIsOpen", isOpen: false });
          }
        }}
      >
        <div className="absolute top-0 right-0">
          <Button
            data-testid="close-find-replace-button"
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
              ref={findInputRef} // Attach the ref here
              data-testid="find-input"
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
              data-testid="replace-input"
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
                    dispatch({
                      type: "setCaseSensitive",
                      caseSensitive: pressed,
                    })
                  }
                >
                  <CaseSensitiveIcon className="w-4 h-4" />
                </Toggle>
              </Tooltip>
              <Tooltip content="Match Whole Word">
                <Toggle
                  size="sm"
                  pressed={state.wholeWord}
                  data-state={state.wholeWord ? "on" : "off"}
                  onPressedChange={(pressed) =>
                    dispatch({ type: "setWholeWord", wholeWord: pressed })
                  }
                >
                  <WholeWordIcon className="w-4 h-4" />
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
                data-testid="replace-next-button"
                size="xs"
                variant="outline"
                className="h-6 text-xs"
                onClick={() => {
                  replaceNext() && resetMatches();
                }}
                disabled={state.findText === ""}
              >
                Replace Next
              </Button>
              <Button
                data-testid="replace-all-button"
                size="xs"
                variant="outline"
                className="h-6 text-xs"
                onClick={() => {
                  const undo = replaceAll();
                  if (!undo) {
                    return;
                  }
                  resetMatches();

                  // Show toast with undo button
                  const { dismiss } = toast({
                    title: "Replaced all occurrences",
                    action: (
                      <UndoButton
                        data-testid="undo-replace-all-button"
                        onClick={() => {
                          undo();
                          dismiss();
                        }}
                      />
                    ),
                  });
                }}
                disabled={state.findText === ""}
              >
                Replace All
              </Button>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Tooltip content="Find Previous">
            <Button
              data-testid="find-prev-button"
              size="xs"
              variant="secondary"
              onClick={() => findPrev()}
            >
              <ArrowLeftIcon className="w-4 h-4" />
            </Button>
          </Tooltip>
          <Tooltip content="Find Next">
            <Button
              data-testid="find-next-button"
              size="xs"
              variant="secondary"
              onClick={() => findNext()}
            >
              <ArrowRightIcon className="w-4 h-4" />
            </Button>
          </Tooltip>
          {matches != null && currentMatch == null && (
            <span className="text-sm">{matches.count} matches</span>
          )}
          {matches != null && currentMatch != null && (
            <span className="text-sm">
              {currentMatch + 1} of {matches.count}
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground flex gap-1 mt-2">
          Press{" "}
          <KeyboardHotkeys
            shortcut={hotkeys.getHotkey("cell.findAndReplace").key}
          />{" "}
          again to open the native browser search.
        </div>
      </div>
    </FocusScope>
  );
};
