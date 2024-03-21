/* Copyright 2024 Marimo. All rights reserved. */
import { useRef, useState } from "react";
import { CheckIcon, XIcon } from "lucide-react";

import { Button } from "@/components/editor/inputs/Inputs";
import {
  DirCompletionInput,
  DirCompletionInputHandle,
} from "@/components/editor/DirCompletionInput";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
  AlertDialogDescription,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export const FilenameForm = ({
  filename,
  setFilename,
}: {
  filename: string | null;
  setFilename: (filename: string | null) => Promise<string | null>;
}): JSX.Element => {
  const { openAlert } = useImperativeModal();
  const placeholderText = filename === null ? "untitled marimo app" : filename;
  const [showButtons, setShowButtons] = useState(false);
  const [validName, setValidName] = useState(false);
  const handle = useRef<DirCompletionInputHandle | null>(null);

  function validateAndSubmitFilenameChange() {
    const inputEl = document.getElementById(
      "filename-input",
    ) as HTMLInputElement | null;
    if (inputEl === null) {
      throw new Error("Could not find filename form");
    }
    const value = inputEl.value;
    if (value.length === 0 || value === ".py") {
      openAlert(
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive">
            Oops!
          </AlertDialogTitle>
          <AlertDialogDescription>
            The filename can't be empty. Make sure to enter a non-empty name.
          </AlertDialogDescription>
        </AlertDialogHeader>,
      );
      inputEl.blur();
    } else if (value.endsWith(".py")) {
      setFilename(value).then(() => {
        inputEl.blur();
      });
    } else {
      setFilename(`${value}.py`).then(() => {
        // wait for setter to resolve before blurring, because blurring
        // resets the underlying value
        inputEl.blur();
      });
    }
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    validateAndSubmitFilenameChange();
  }

  // MouseDown is fired before Blur
  function handleMouseDown(e: React.MouseEvent<HTMLButtonElement>) {
    e.preventDefault();
    validateAndSubmitFilenameChange();
  }

  function onFocus() {
    setShowButtons(true);
  }

  function onBlur() {
    // TODO(akshayka): if tabbed to button, buttons (and input value)
    // should remain visible
    setShowButtons(false);
  }

  function onChange(value: string) {
    const completionHandle = handle.current;
    if (completionHandle === null) {
      return;
    }

    const candidate = value.endsWith(".py") ? value : `${value}.py`;
    if (
      // name should not be ".py"
      candidate.length > 3 &&
      // file should not already exist
      !completionHandle.suggestions.includes(candidate)
    ) {
      setValidName(true);
    } else {
      setValidName(false);
    }
  }

  const buttonVis = showButtons ? "visible" : "hidden";
  return (
    <div id="Filename">
      <form id="filename-form" onSubmit={handleSubmit}>
        <div /> {/* empty element as grid spacer */}
        <div style={{ position: "relative" }}>
          <DirCompletionInput
            placeholderText={placeholderText}
            initialValue={filename}
            onChangeCallback={onChange}
            onFocusCallback={onFocus}
            onBlurCallback={onBlur}
            resetOnBlur={true}
            flexibleWidth={true}
            handle={handle}
            id="filename-input"
            className={filename === null ? "missing-filename" : "filename"}
          />
          <Button
            type="submit"
            data-testid="filename-form-submit-button"
            color={validName ? "green" : "gray"}
            onMouseDown={handleMouseDown}
            style={{
              marginRight: "0px",
              padding: "0px",
              position: "absolute",
              top: "0.25rem",
              right: "-44px",
              width: "30px",
              height: "30px",
              visibility: buttonVis,
            }}
          >
            <CheckIcon size={16} strokeWidth={1.5} />
          </Button>
          <Button
            color="gray"
            data-testid="filename-form-cancel-button"
            style={{
              marginRight: "0px",
              padding: "0px",
              position: "absolute",
              top: "0.25rem",
              right: "-86px",
              width: "30px",
              height: "30px",
              visibility: buttonVis,
            }}
          >
            <XIcon size={16} strokeWidth={1.5} />
          </Button>
        </div>
      </form>
    </div>
  );
};
