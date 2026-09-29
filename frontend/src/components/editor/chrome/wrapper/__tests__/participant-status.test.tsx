/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import type React from "react";
import { describe, expect, it } from "vitest";
import { PAIR_PREVIEW } from "@/__tests__/fixtures/pair-preview";
import { TooltipProvider } from "@/components/ui/tooltip";
import { pairPreviewAtom } from "@/core/config/pair";
import {
  type ParticipantPresence,
  participantPresenceAtom,
} from "@/core/participants/state";
import { ParticipantStatus } from "../footer-items/participant-status";

const CONNECTED: ParticipantPresence = {
  op: "participant-presence",
  active: false,
  active_since: null,
  attached: true,
  harness: { id: "pi", displayName: "Pi" },
  kind: "agent",
  last_contact_at: Date.now() / 1000,
  listening: false,
  participant_id: "abcdef1234567890",
};

function renderStatus(
  options: {
    pairPreview?: typeof PAIR_PREVIEW | undefined;
    presence?: ParticipantPresence | null;
  } = {},
) {
  const pairPreview = Object.hasOwn(options, "pairPreview")
    ? options.pairPreview
    : PAIR_PREVIEW;
  const presence = Object.hasOwn(options, "presence")
    ? (options.presence ?? null)
    : CONNECTED;
  const store = createStore();
  store.set(pairPreviewAtom, pairPreview);
  store.set(participantPresenceAtom, presence);
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>
      <TooltipProvider>{children}</TooltipProvider>
    </Provider>
  );
  return render(<ParticipantStatus />, { wrapper });
}

describe("ParticipantStatus", () => {
  it("renders nothing without Pair preview or a presence snapshot", () => {
    const withoutPreview = renderStatus({ pairPreview: undefined });
    expect(withoutPreview.container).toBeEmptyDOMElement();
    withoutPreview.unmount();

    const withoutPresence = renderStatus({ presence: null });
    expect(withoutPresence.container).toBeEmptyDOMElement();
  });

  it("shows connected participant details", () => {
    renderStatus();

    const item = screen.getByTestId("footer-participant-status");
    expect(item).toHaveTextContent("Pi");
    expect(item).toHaveAccessibleName("Pi: Connected");

    fireEvent.click(item);
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(
      screen.getByText("Pi connects through marimo pair."),
    ).toBeInTheDocument();
    expect(screen.getByText("Last contact")).toBeInTheDocument();
    expect(screen.getByText("abcdef12")).toBeInTheDocument();
    expect(screen.queryByText("Model")).not.toBeInTheDocument();
  });

  it("shows a disconnected participant", () => {
    renderStatus({ presence: { ...CONNECTED, attached: false } });

    const item = screen.getByTestId("footer-participant-status");
    expect(item).toHaveAccessibleName("Pi: Disconnected");
    fireEvent.click(item);
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("uses the self-described harness name", () => {
    renderStatus({
      presence: {
        ...CONNECTED,
        harness: { id: "custom", displayName: "My Agent" },
      },
    });

    const item = screen.getByTestId("footer-participant-status");
    expect(item).toHaveTextContent("My Agent");
    fireEvent.click(item);
    expect(screen.queryByText("Model")).not.toBeInTheDocument();
  });
});
