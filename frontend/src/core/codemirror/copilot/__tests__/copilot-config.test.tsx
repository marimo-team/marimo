/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { CopilotConfig } from "../copilot-config";
import { getCopilotClient } from "../client";
import { toast } from "@/components/ui/use-toast";
import type { CopilotLanguageServerClient } from "../language-server";
import { useAtom } from "jotai";
import { Provider as JotaiProvider } from "jotai";

// Mock dependencies
vi.mock("../client", () => ({
  getCopilotClient: vi.fn(),
}));

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

vi.mock("jotai", () => ({
  useAtom: vi.fn().mockImplementation(() => {
    return [false, vi.fn()] as [boolean, (value: boolean) => void];
  }),
}));

describe("CopilotConfig", () => {
  // Create a mock with just the methods we need for testing
  let mockClient: Pick<
    CopilotLanguageServerClient,
    | "initializePromise"
    | "signedIn"
    | "signInInitiate"
    | "signInConfirm"
    | "signOut"
  >;

  beforeEach(() => {
    mockClient = {
      initializePromise: Promise.resolve(),
      signedIn: vi.fn().mockResolvedValue(false),
      signInInitiate: vi.fn().mockResolvedValue({
        status: "OK",
        verificationUri: "https://github.com/login",
        userCode: "123456",
      }),
      signInConfirm: vi.fn().mockResolvedValue({ status: "OK" }),
      signOut: vi.fn().mockResolvedValue(undefined),
    };
    vi.mocked(getCopilotClient).mockReturnValue(
      mockClient as CopilotLanguageServerClient,
    );
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  it("shows sign-in button when not signed in", async () => {
    render(
      <JotaiProvider>
        <CopilotConfig />
      </JotaiProvider>,
    );
    await waitFor(() => {
      expect(screen.getByText("Sign in to GitHub Copilot")).toBeInTheDocument();
    });
  });

  it("handles successful sign-in flow", async () => {
    render(
      <JotaiProvider>
        <CopilotConfig />
      </JotaiProvider>,
    );
    // Click sign in button
    const signInButton = await screen.findByText("Sign in to GitHub Copilot");
    fireEvent.click(signInButton);

    // Verify sign-in steps are shown
    await waitFor(() => {
      expect(screen.getByText(/Copy this code/)).toBeInTheDocument();
      expect(screen.getByText("123456")).toBeInTheDocument();
    });

    // Click done button
    const doneButton = screen.getByText("Done");
    fireEvent.click(doneButton);

    // Verify success state
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  });

  it("shows toast on connection error", async () => {
    // Mock connection failure
    mockClient.initializePromise = Promise.reject(new Error("ECONNREFUSED"));

    render(
      <JotaiProvider>
        <CopilotConfig />
      </JotaiProvider>,
    );

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "GitHub Copilot Connection Error",
          variant: "danger",
        }),
      );
    });
  });

  it("retries sign-in confirmation on failure", async () => {
    render(
      <JotaiProvider>
        <CopilotConfig />
      </JotaiProvider>,
    );

    // Mock initial failure then success
    mockClient.signInConfirm = vi
      .fn()
      .mockRejectedValueOnce(new Error("Failed"))
      .mockResolvedValueOnce({ status: "OK" });
    mockClient.signedIn = vi.fn().mockResolvedValueOnce(true);

    // Start sign-in flow
    const signInButton = await screen.findByText("Sign in to GitHub Copilot");
    fireEvent.click(signInButton);

    // Click done button
    const doneButton = await screen.findByText("Done");
    fireEvent.click(doneButton);

    // Verify retry was attempted and succeeded
    await waitFor(() => {
      expect(mockClient.signedIn).toHaveBeenCalled();
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  });

  it("handles sign-out", async () => {
    // Start in signed-in state
    vi.mocked(useAtom).mockImplementation(() => [true, vi.fn()]);

    render(
      <JotaiProvider>
        <CopilotConfig />
      </JotaiProvider>,
    );

    // Click disconnect button
    const disconnectButton = await screen.findByText("Disconnect");
    fireEvent.click(disconnectButton);

    // Verify UI updates immediately
    await waitFor(() => {
      expect(screen.getByText("Sign in to GitHub Copilot")).toBeInTheDocument();
    });
  });

  it("shows connection error state with retry button", async () => {
    // Mock connection error during sign-in
    mockClient.signInConfirm = vi
      .fn()
      .mockRejectedValue(new Error("ECONNREFUSED"));

    render(
      <JotaiProvider>
        <CopilotConfig />
      </JotaiProvider>,
    );

    // Start sign-in flow
    const signInButton = await screen.findByText("Sign in to GitHub Copilot");
    fireEvent.click(signInButton);

    // Click done button
    const doneButton = await screen.findByText("Done");
    fireEvent.click(doneButton);

    // Verify connection error state
    await waitFor(() => {
      expect(screen.getByText("Connection Error")).toBeInTheDocument();
      expect(screen.getByText("Retry Connection")).toBeInTheDocument();
      expect(toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "GitHub Copilot Connection Error",
          variant: "danger",
        }),
      );
    });
  });
});
