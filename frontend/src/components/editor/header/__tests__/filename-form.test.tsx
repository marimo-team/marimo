/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { fireEvent, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FilenameForm } from "../filename-form";

// Mock the hooks
vi.mock("@/core/saving/filename", () => ({
  useUpdateFilename: vi.fn(),
}));

vi.mock("@/core/saving/save-component", () => ({
  useSaveNotebook: vi.fn(),
}));

// Mock FilenameInput to make testing easier
vi.mock("@/components/editor/header/filename-input", () => ({
  FilenameInput: ({
    onNameChange,
    initialValue,
  }: {
    onNameChange: (value: string) => void;
    initialValue?: string | null;
  }) => (
    <input
      data-testid="filename-input"
      data-initial-value={initialValue || ""}
      onChange={(e) => onNameChange(e.target.value)}
    />
  ),
}));

const mockUseUpdateFilename = vi.mocked(
  await import("@/core/saving/filename"),
).useUpdateFilename;

const mockUseSaveNotebook = vi.mocked(
  await import("@/core/saving/save-component"),
).useSaveNotebook;

describe("FilenameForm", () => {
  const mockUpdateFilename = vi.fn();
  const mockSaveNotebook = vi.fn();
  const mockSaveOrNameNotebook = vi.fn();
  const mockSaveIfNotebookIsPersistent = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    mockUseUpdateFilename.mockReturnValue(mockUpdateFilename);
    mockUseSaveNotebook.mockReturnValue({
      saveNotebook: mockSaveNotebook,
      saveOrNameNotebook: mockSaveOrNameNotebook,
      saveIfNotebookIsPersistent: mockSaveIfNotebookIsPersistent,
    });
  });

  it("should call saveNotebook when creating a new file from an unnamed notebook", async () => {
    // Setup: updateFilename resolves with the new filename
    mockUpdateFilename.mockResolvedValue("/path/to/new-file.py");

    const { getByTestId } = render(<FilenameForm filename={null} />);

    const input = getByTestId("filename-input");

    // Simulate name change (user entering a filename)
    fireEvent.change(input, { target: { value: "new-file.py" } });

    // Wait for the promise to resolve
    await waitFor(() => {
      expect(mockUpdateFilename).toHaveBeenCalledWith("new-file.py");
    });

    await waitFor(() => {
      expect(mockSaveNotebook).toHaveBeenCalledWith(
        "/path/to/new-file.py",
        true,
      );
    });
  });

  it("should not call saveNotebook when renaming an existing file", async () => {
    // Setup: updateFilename resolves with the new filename
    mockUpdateFilename.mockResolvedValue("/path/to/renamed-file.py");

    const { getByTestId } = render(
      <FilenameForm filename="/path/to/existing-file.py" />,
    );

    const input = getByTestId("filename-input");

    // Simulate name change
    fireEvent.change(input, { target: { value: "renamed-file.py" } });

    // Wait for the promise to resolve
    await waitFor(() => {
      expect(mockUpdateFilename).toHaveBeenCalledWith("renamed-file.py");
    });

    // saveNotebook should NOT be called because the file was already named
    expect(mockSaveNotebook).not.toHaveBeenCalled();
  });

  it("should not call saveNotebook when updateFilename returns null", async () => {
    // Setup: updateFilename resolves with null (e.g., user cancelled or error)
    mockUpdateFilename.mockResolvedValue(null);

    const { getByTestId } = render(<FilenameForm filename={null} />);

    const input = getByTestId("filename-input");

    // Simulate name change
    fireEvent.change(input, { target: { value: "new-file.py" } });

    // Wait for the promise to resolve
    await waitFor(() => {
      expect(mockUpdateFilename).toHaveBeenCalled();
    });

    // saveNotebook should NOT be called because updateFilename returned null
    expect(mockSaveNotebook).not.toHaveBeenCalled();
  });
});
