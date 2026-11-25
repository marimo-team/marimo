/* Copyright 2026 Marimo. All rights reserved. */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModalProvider } from "@/components/modal/ImperativeModal";
import type { ListSecretKeysResponse } from "@/core/network/types";
import SecretsPanel from "../secrets-panel";
import { filterSecretKeys } from "../secrets-utils";

const { providers } = vi.hoisted(() => {
  const providers: ListSecretKeysResponse["keys"] = [
    { name: ".env", provider: "dotenv", keys: ["OPENAI_API_KEY", "DB_URL"] },
    { name: "Environment", provider: "env", keys: ["HOME", "OPENAI_ORG"] },
  ];
  return { providers };
});

vi.mock("@/core/secrets/request-registry", () => ({
  SECRETS_REGISTRY: {
    request: vi.fn(async () => ({ secrets: providers })),
  },
}));

describe("filterSecretKeys", () => {
  it("returns all providers for an empty or blank search", () => {
    expect(filterSecretKeys(providers, "")).toEqual(providers);
    expect(filterSecretKeys(providers, "   ")).toEqual(providers);
  });

  it("matches part of a key, ignoring case and surrounding spaces, and drops providers with no match", () => {
    expect(filterSecretKeys(providers, "  url ")).toEqual([
      { name: ".env", provider: "dotenv", keys: ["DB_URL"] },
    ]);
  });
});

describe("SecretsPanel", () => {
  it("filters the table as the user types", async () => {
    render(
      <ModalProvider>
        <SecretsPanel />
      </ModalProvider>,
    );

    const search = await screen.findByRole("textbox", {
      name: "Search environment variables",
    });

    fireEvent.change(search, { target: { value: "openai" } });
    expect(screen.getByText("OPENAI_API_KEY")).toBeInTheDocument();
    expect(screen.getByText("OPENAI_ORG")).toBeInTheDocument();
    expect(screen.queryByText("DB_URL")).not.toBeInTheDocument();
    expect(screen.queryByText("HOME")).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "missing" } });
    expect(screen.getByText("No results")).toBeInTheDocument();
  });
});
