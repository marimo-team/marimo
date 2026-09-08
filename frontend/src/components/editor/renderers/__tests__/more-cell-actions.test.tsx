/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { MoreCellActions } from "../more-cell-actions";

beforeAll(() => {
  // jsdom does not implement scrollIntoView, which cmdk uses to focus items.
  global.HTMLElement.prototype.scrollIntoView = vi.fn();
});

const renderActions = () => {
  const onSelectRecipe = vi.fn();
  const onConnectData = vi.fn();
  const onBrowseRecipes = vi.fn();
  const onGenerateWithAI = vi.fn();

  render(
    <MoreCellActions
      buttonClassName=""
      disabled={false}
      onSelectRecipe={onSelectRecipe}
      onConnectData={onConnectData}
      onBrowseRecipes={onBrowseRecipes}
      generateWithAI={{
        description: "Describe the cell you want to create",
        onSelect: onGenerateWithAI,
      }}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "More" }));
  return {
    onSelectRecipe,
    onConnectData,
    onBrowseRecipes,
    onGenerateWithAI,
  };
};

describe("MoreCellActions", () => {
  it("shows goal-oriented cell actions", () => {
    renderActions();

    expect(screen.getByText("Add an interactive control")).toBeVisible();
    expect(screen.getByText("Generate with AI")).toBeVisible();
    expect(screen.getByText("Build a form")).toBeVisible();
    expect(screen.getByText("Read a CSV with DuckDB")).toBeVisible();
    expect(screen.getByText("Create a reactive Altair plot")).toBeVisible();
    expect(screen.getByText("Connect to data")).toBeVisible();
    expect(screen.getByText("Browse all snippets")).toBeVisible();

    expect(screen.getByText("Data").parentElement).toHaveTextContent(
      "Read a CSV with DuckDB",
    );
    expect(screen.getByText("Build").parentElement).not.toHaveTextContent(
      "Read a CSV with DuckDB",
    );
  });

  it("selects Generate with AI and closes the menu", () => {
    const { onGenerateWithAI } = renderActions();

    fireEvent.click(screen.getByText("Generate with AI"));

    expect(onGenerateWithAI).toHaveBeenCalledOnce();
    expect(screen.queryByPlaceholderText("Search actions...")).toBeNull();
  });

  it("selects a recipe and closes the menu", () => {
    const { onSelectRecipe } = renderActions();

    fireEvent.click(screen.getByText("Build a form"));

    expect(onSelectRecipe).toHaveBeenCalledWith("form");
    expect(screen.queryByPlaceholderText("Search actions...")).toBeNull();
  });

  it("searches action descriptions and keywords", () => {
    renderActions();

    fireEvent.change(screen.getByPlaceholderText("Search actions..."), {
      target: { value: "submit" },
    });

    expect(screen.getByText("Build a form")).toBeVisible();
    expect(screen.queryByText("Add an interactive control")).toBeNull();
    expect(screen.queryByText("Connect to data")).toBeNull();
  });
});
