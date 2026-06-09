/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FormWrapper } from "../FormPlugin";


describe("FormPlugin", () => {
  it("submits the form on Ctrl+Enter and calls setValue", async () => {
    const setValue = vi.fn();
    const validate = vi.fn().mockResolvedValue(null);

    render(
      <FormWrapper
        currentValue="old-val"
        newValue="new-val"
        setValue={setValue}
        validate={validate}
        shouldValidate={false}
        clearOnSubmit={false}
        submitButtonLabel="Submit"
        bordered={true}
        loading={false}
        submitButtonDisabled={false}
        showClearButton={false}
        clearButtonLabel="Clear"
        label={null}
      >
        <input data-testid="input" />
      </FormWrapper>
    );

    const input = screen.getByTestId("input");

    // Simulate Ctrl+Enter on input
    fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });

    await waitFor(() => {
      expect(setValue).toHaveBeenCalledWith("new-val");
    });
  });

  it("submits the form on Ctrl+Enter and runs validation when shouldValidate is true", async () => {
    const setValue = vi.fn();
    const validate = vi.fn().mockResolvedValue("Validation failed message");

    render(
      <FormWrapper
        currentValue="old-val"
        newValue="new-val"
        setValue={setValue}
        validate={validate}
        shouldValidate={true}
        clearOnSubmit={false}
        submitButtonLabel="Submit"
        bordered={true}
        loading={false}
        submitButtonDisabled={false}
        showClearButton={false}
        clearButtonLabel="Clear"
        label={null}
      >
        <input data-testid="input" />
      </FormWrapper>
    );

    const input = screen.getByTestId("input");

    // Simulate Ctrl+Enter on input
    fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });

    await waitFor(() => {
      expect(validate).toHaveBeenCalledWith({ value: "new-val" });
      // should not submit (setValue not called) due to validation failure
      expect(setValue).not.toHaveBeenCalled();
      // error message displayed
      expect(screen.getByText("Validation failed message")).toBeInTheDocument();
    });
  });

  it("clears inputs on submission when clearOnSubmit is true", async () => {
    const setValue = vi.fn();
    const validate = vi.fn().mockResolvedValue(null);

    let mockUIElement: HTMLElement & { reset?: () => void } | null = null;
    const mockReset = vi.fn();

    render(
      <FormWrapper
        currentValue="old-val"
        newValue="new-val"
        setValue={setValue}
        validate={validate}
        shouldValidate={false}
        clearOnSubmit={true}
        submitButtonLabel="Submit"
        bordered={true}
        loading={false}
        submitButtonDisabled={false}
        showClearButton={false}
        clearButtonLabel="Clear"
        label={null}
      >
        <div
          ref={(el) => {
            if (el && !mockUIElement) {
              mockUIElement = document.createElement("marimo-ui-element");
              mockUIElement.setAttribute("data-testid", "mock-ui-element");
              mockUIElement.reset = mockReset;
              const inputEl = document.createElement("input");
              inputEl.type = "text";
              mockUIElement.appendChild(inputEl);
              el.appendChild(mockUIElement);
            }
          }}
        />
      </FormWrapper>
    );

    const input = screen.getByRole("textbox");

    // Simulate Ctrl+Enter on input
    fireEvent.keyDown(input, { key: "Enter", ctrlKey: true });

    await waitFor(() => {
      expect(setValue).toHaveBeenCalledWith("new-val");
      expect(mockReset).toHaveBeenCalled();
    });
  });

  it("does not submit on Shift+Enter", async () => {
    const setValue = vi.fn();
    const validate = vi.fn().mockResolvedValue(null);

    render(
      <FormWrapper
        currentValue="old-val"
        newValue="new-val"
        setValue={setValue}
        validate={validate}
        shouldValidate={false}
        clearOnSubmit={false}
        submitButtonLabel="Submit"
        bordered={true}
        loading={false}
        submitButtonDisabled={false}
        showClearButton={false}
        clearButtonLabel="Clear"
        label={null}
      >
        <input data-testid="input" />
      </FormWrapper>
    );

    const input = screen.getByTestId("input");

    // Simulate Shift+Enter on input
    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });

    // Wait a bit to ensure it wasn't triggered
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(setValue).not.toHaveBeenCalled();
    expect(validate).not.toHaveBeenCalled();
  });
});
