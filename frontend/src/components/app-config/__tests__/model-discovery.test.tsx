/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listProviderModels } from "@/core/network/ai";
import { HTTPError } from "@/utils/errors";
import { ModelDiscovery } from "../model-discovery";

vi.mock("@/core/network/ai", () => ({ listProviderModels: vi.fn() }));
vi.mock("@/core/wasm/utils", () => ({ isWasm: () => false }));

function Discovery({ configuration = "saved", disabled = false }) {
  const [value, setValue] = useState("");
  return (
    <ModelDiscovery
      key={configuration}
      provider="gateway"
      label="Model"
      inputId="model"
      disabled={disabled}
      value={value}
      onValueChange={setValue}
    />
  );
}

const search = () =>
  screen.getByRole("button", { name: "Search available models" });

describe("ModelDiscovery", () => {
  beforeEach(() => vi.mocked(listProviderModels).mockReset());

  it("loads on demand and fills the editable model field on selection", async () => {
    vi.mocked(listProviderModels).mockResolvedValue({
      models: [{ id: "org/model", name: "Model name" }],
    });
    render(<Discovery />);
    expect(listProviderModels).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText("Model"), {
      target: { value: "manual-id" },
    });
    expect(screen.getByLabelText("Model")).toHaveValue("manual-id");
    fireEvent.change(screen.getByLabelText("Model"), { target: { value: "" } });
    fireEvent.click(search());
    await screen.findByRole("button", { name: "Model name — org/model" });
    fireEvent.keyDown(screen.getByLabelText("Model"), { key: "Escape" });
    fireEvent.keyDown(screen.getByLabelText("Model"), { key: "ArrowDown" });
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Model name — org/model" }),
      ).toHaveFocus(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Model name — org/model" }),
    );

    expect(listProviderModels).toHaveBeenCalledExactlyOnceWith("gateway");
    expect(screen.getByLabelText("Model")).toHaveValue("org/model");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows backend error details and allows retrying", async () => {
    vi.mocked(listProviderModels)
      .mockRejectedValueOnce(
        new HTTPError(400, "Bad Request", {
          detail: "Provider rejected credentials.",
        }),
      )
      .mockResolvedValueOnce({ models: [] });
    render(<Discovery />);
    fireEvent.click(search());
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Provider rejected credentials.",
    );

    fireEvent.click(search());
    expect(await screen.findByText("No models found")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps focus in the input when reopening after navigating an open catalog", async () => {
    vi.mocked(listProviderModels).mockResolvedValue({
      models: [{ id: "model-a", name: "Model A" }],
    });
    render(<Discovery />);
    fireEvent.click(search());
    const option = await screen.findByRole("button", {
      name: "Model A — model-a",
    });
    const input = screen.getByLabelText("Model");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(option).toHaveFocus();
    fireEvent.keyDown(input, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );

    act(() => input.focus());
    await screen.findByRole("dialog");
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("discards outstanding results when the saved configuration changes", async () => {
    const pending =
      Promise.withResolvers<Awaited<ReturnType<typeof listProviderModels>>>();
    vi.mocked(listProviderModels).mockReturnValueOnce(pending.promise);
    const { rerender } = render(<Discovery />);
    fireEvent.click(search());
    await waitFor(() => expect(listProviderModels).toHaveBeenCalledOnce());

    rerender(<Discovery configuration="changed" disabled={true} />);
    expect(search()).toBeDisabled();
    await act(async () =>
      pending.resolve({ models: [{ id: "stale", name: "Stale model" }] }),
    );
    expect(screen.queryByText("Stale model — stale")).not.toBeInTheDocument();

    rerender(<Discovery configuration="saved-again" />);
    expect(search()).toBeEnabled();
    expect(listProviderModels).toHaveBeenCalledOnce();
  });
});
