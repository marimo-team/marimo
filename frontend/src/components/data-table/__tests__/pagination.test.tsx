/* Copyright 2026 Marimo. All rights reserved. */

import { getCoreRowModel, useReactTable } from "@tanstack/react-table";
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { DataTablePagination, matchingPageRanges } from "../pagination";

function PaginationHarness({
  totalPages = 3,
  loading = false,
}: {
  totalPages?: number;
  loading?: boolean;
}) {
  const table = useReactTable({
    locale: "en-US",
    data: [],
    columns: [],
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: totalPages,
  });
  return (
    <TooltipProvider>
      <DataTablePagination table={table} tableLoading={loading} />
    </TooltipProvider>
  );
}

test("named navigation controls preserve page updates and boundaries", () => {
  render(<PaginationHarness />);
  expect(screen.getByRole("button", { name: "First page" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  expect(
    screen.getByRole("button", { name: "Choose page, current page 2 of 3" }),
  ).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "Last page" }));
  expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Last page" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
  fireEvent.click(screen.getByRole("button", { name: "First page" }));
  expect(
    screen.getByRole("button", { name: "Choose page, current page 1 of 3" }),
  ).toBeEnabled();
  expect(screen.getByRole("button", { name: "First page" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Next page" })).toBeEnabled();
  expect(screen.getByRole("button", { name: "Last page" })).toBeEnabled();
});

test("loading prevents navigation and a single page disables controls", () => {
  const { rerender } = render(<PaginationHarness loading={true} />);
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  fireEvent.click(screen.getByRole("button", { name: "Last page" }));
  expect(
    screen.getByRole("button", { name: "Choose page, current page 1 of 3" }),
  ).toBeEnabled();
  rerender(<PaginationHarness />);
  fireEvent.click(screen.getByRole("button", { name: "Next page" }));
  expect(
    screen.getByRole("button", { name: "Choose page, current page 2 of 3" }),
  ).toBeEnabled();
  rerender(<PaginationHarness key="single-page" totalPages={1} />);
  for (const name of [
    "First page",
    "Previous page",
    "Next page",
    "Last page",
    "Choose page, current page 1 of 1",
  ]) {
    expect(screen.getByRole("button", { name })).toBeDisabled();
  }
});

test("page picker exposes named dialog and search", () => {
  render(<PaginationHarness />);
  fireEvent.click(
    screen.getByRole("button", { name: "Choose page, current page 1 of 3" }),
  );
  expect(
    screen.getByRole("dialog", { name: "Choose page" }),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("combobox", { name: "Search pages" }),
  ).toBeInTheDocument();
});

test("empty prefix returns no ranges", () => {
  expect(matchingPageRanges("", 500)).toEqual([]);
});

test("zero prefix returns no ranges", () => {
  expect(matchingPageRanges("0", 500)).toEqual([]);
});

test("leading-zero prefix returns no ranges", () => {
  expect(matchingPageRanges("01", 500)).toEqual([]);
});

test("single digit prefix", () => {
  expect(matchingPageRanges("5", 500)).toEqual([
    [5, 5],
    [50, 59],
    [500, 500],
  ]);
});

test("single digit prefix with exact totalPages boundary", () => {
  expect(matchingPageRanges("5", 55)).toEqual([
    [5, 5],
    [50, 55],
  ]);
});

test("multi-digit prefix", () => {
  expect(matchingPageRanges("12", 5000)).toEqual([
    [12, 12],
    [120, 129],
    [1200, 1299],
  ]);
});

test("prefix larger than totalPages returns no ranges", () => {
  expect(matchingPageRanges("999", 100)).toEqual([]);
});

test("prefix equal to totalPages", () => {
  expect(matchingPageRanges("100", 100)).toEqual([[100, 100]]);
});

test("prefix 1 with small totalPages", () => {
  expect(matchingPageRanges("1", 10)).toEqual([
    [1, 1],
    [10, 10],
  ]);
});

test("prefix 1 with totalPages=1", () => {
  expect(matchingPageRanges("1", 1)).toEqual([[1, 1]]);
});
