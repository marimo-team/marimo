/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { SetupMocks } from "@/__mocks__/common";
import { FormWrapper, type FormWrapperProps } from "../FormPlugin";

beforeAll(() => {
  SetupMocks.resizeObserver();
});

function renderForm(overrides: Partial<FormWrapperProps<string>> = {}) {
  const setValue = vi.fn();
  const validate = vi.fn().mockResolvedValue(null);

  render(
    <FormWrapper<string>
      label={null}
      bordered={false}
      loading={false}
      submitButtonLabel="Submit"
      submitButtonDisabled={false}
      clearOnSubmit={false}
      showClearButton={false}
      clearButtonLabel="Clear"
      currentValue="old"
      newValue="new"
      setValue={setValue}
      validate={validate}
      shouldValidate={false}
      {...overrides}
    >
      <input data-testid="inner-input" />
    </FormWrapper>,
  );

  return { setValue, validate };
}

describe("FormWrapper — submit button", () => {
  it("calls setValue when the submit button is clicked", async () => {
    const { setValue } = renderForm();
    fireEvent.click(screen.getByTestId("marimo-plugin-form-submit-button"));
    await waitFor(() => expect(setValue).toHaveBeenCalledWith("new"));
  });

  it("does NOT call setValue when shouldValidate=true and validate returns an error", async () => {
    const validate = vi.fn().mockResolvedValue("Invalid input");
    const { setValue } = renderForm({ shouldValidate: true, validate });
    fireEvent.click(screen.getByTestId("marimo-plugin-form-submit-button"));
    await waitFor(() =>
      expect(screen.getByText("Invalid input")).toBeInTheDocument(),
    );
    expect(setValue).not.toHaveBeenCalled();
  });

  it("calls setValue when shouldValidate=true and validate returns null", async () => {
    const validate = vi.fn().mockResolvedValue(null);
    const { setValue } = renderForm({ shouldValidate: true, validate });
    fireEvent.click(screen.getByTestId("marimo-plugin-form-submit-button"));
    await waitFor(() => expect(setValue).toHaveBeenCalledWith("new"));
  });
});

describe("FormWrapper — Ctrl+Enter / Cmd+Enter", () => {
  it("submits (calls setValue) on Ctrl+Enter", async () => {
    const { setValue } = renderForm();
    const form = screen
      .getByTestId("marimo-plugin-form-submit-button")
      .closest("form")!;
    // requestSubmit is not implemented in jsdom — spy on it and trigger submit
    const requestSubmit = vi
      .spyOn(form, "requestSubmit")
      .mockImplementation(() => {
        fireEvent.submit(form);
      });

    fireEvent.keyDown(form.firstElementChild!, {
      key: "Enter",
      ctrlKey: true,
    });

    expect(requestSubmit).toHaveBeenCalled();
    await waitFor(() => expect(setValue).toHaveBeenCalledWith("new"));
  });

  it("submits (calls setValue) on Cmd+Enter (metaKey)", async () => {
    const { setValue } = renderForm();
    const form = screen
      .getByTestId("marimo-plugin-form-submit-button")
      .closest("form")!;
    vi.spyOn(form, "requestSubmit").mockImplementation(() => {
      fireEvent.submit(form);
    });

    fireEvent.keyDown(form.firstElementChild!, {
      key: "Enter",
      metaKey: true,
    });

    await waitFor(() => expect(setValue).toHaveBeenCalledWith("new"));
  });

  it("runs validation on Ctrl+Enter when shouldValidate=true", async () => {
    const validate = vi.fn().mockResolvedValue("Bad value");
    const { setValue } = renderForm({ shouldValidate: true, validate });
    const form = screen
      .getByTestId("marimo-plugin-form-submit-button")
      .closest("form")!;
    vi.spyOn(form, "requestSubmit").mockImplementation(() => {
      fireEvent.submit(form);
    });

    fireEvent.keyDown(form.firstElementChild!, {
      key: "Enter",
      ctrlKey: true,
    });

    await waitFor(() =>
      expect(screen.getByText("Bad value")).toBeInTheDocument(),
    );
    expect(setValue).not.toHaveBeenCalled();
  });

  it("applies clearOnSubmit on Ctrl+Enter", async () => {
    const { setValue } = renderForm({ clearOnSubmit: true });
    const form = screen
      .getByTestId("marimo-plugin-form-submit-button")
      .closest("form")!;
    vi.spyOn(form, "requestSubmit").mockImplementation(() => {
      fireEvent.submit(form);
    });

    fireEvent.keyDown(form.firstElementChild!, {
      key: "Enter",
      ctrlKey: true,
    });

    await waitFor(() => expect(setValue).toHaveBeenCalledWith("new"));
  });

  it("does NOT submit on plain Enter (no modifier)", () => {
    const { setValue } = renderForm();
    const form = screen
      .getByTestId("marimo-plugin-form-submit-button")
      .closest("form")!;
    const requestSubmit = vi.spyOn(form, "requestSubmit");

    fireEvent.keyDown(form.firstElementChild!, { key: "Enter" });

    expect(requestSubmit).not.toHaveBeenCalled();
    expect(setValue).not.toHaveBeenCalled();
  });
});

describe("FormWrapper — clear button", () => {
  it("renders a clear button when showClearButton=true", () => {
    renderForm({ showClearButton: true });
    expect(
      screen.getByTestId("marimo-plugin-form-clear-button"),
    ).toBeInTheDocument();
  });

  it("does NOT render a clear button when showClearButton=false", () => {
    renderForm({ showClearButton: false });
    expect(
      screen.queryByTestId("marimo-plugin-form-clear-button"),
    ).not.toBeInTheDocument();
  });
});

describe("FormWrapper — loading state", () => {
  it("disables the submit button when loading=true", () => {
    renderForm({ loading: true });
    expect(
      screen.getByTestId("marimo-plugin-form-submit-button"),
    ).toBeDisabled();
  });

  it("disables the submit button when submitButtonDisabled=true", () => {
    renderForm({ submitButtonDisabled: true });
    expect(
      screen.getByTestId("marimo-plugin-form-submit-button"),
    ).toBeDisabled();
  });
});
