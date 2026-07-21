/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { Provider } from "jotai";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { Dialog } from "@/components/ui/dialog";
import { requestClientAtom } from "@/core/network/requests";
import type { EnvironmentInfo } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import * as copyModule from "@/utils/copy";
import { FeedbackModal } from "../feedback-button";

vi.mock("@/utils/copy", () => ({
	copyToClipboard: vi.fn(),
}));

const environment: EnvironmentInfo = {
	marimo: "1.2.3",
	editable: false,
	location: "~/.venv/site-packages/marimo",
	OS: "Darwin",
	"OS Version": "25.0",
	Processor: "arm",
	"Python Version": "3.12.9",
	Locale: "en_US",
	Binaries: { Browser: "chrome 140", Node: "v22", uv: "0.11" },
	Dependencies: { click: "8.4.2" },
	"Optional Dependencies": { pandas: "3.0.0" },
	"Experimental Flags": {},
};

function wrapper({ children }: { children: React.ReactNode }) {
	return (
		<Provider store={store}>
			<Dialog open={true}>{children}</Dialog>
		</Provider>
	);
}

describe("FeedbackModal issue reporting", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		store.set(requestClientAtom, MockRequestClient.create());
	});

	it("loads and previews issue environment details", async () => {
		store.set(
			requestClientAtom,
			MockRequestClient.create({
				getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
			}),
		);
		render(<FeedbackModal onClose={vi.fn()} />, { wrapper });

		expect(screen.getByText("Loading environment details…")).toBeVisible();
		await screen.findByText("Environment details");
		expect(screen.getByText(/"marimo": "1.2.3"/)).toBeInTheDocument();
	});

	it("copies partial details when the environment request fails", async () => {
		store.set(
			requestClientAtom,
			MockRequestClient.create({
				getEnvironmentInfo: vi.fn().mockRejectedValue(new Error("offline")),
			}),
		);
		render(<FeedbackModal onClose={vi.fn()} />, { wrapper });

		await screen.findByText("Server environment information unavailable");
		fireEvent.click(screen.getByRole("button", { name: "Copy issue details" }));
		await waitFor(() =>
			expect(copyModule.copyToClipboard).toHaveBeenCalledWith(
				expect.stringContaining("Environment Collection Error"),
			),
		);
	});

	it("copies raw environment JSON", async () => {
		store.set(
			requestClientAtom,
			MockRequestClient.create({
				getEnvironmentInfo: vi.fn().mockResolvedValue(environment),
			}),
		);
		render(<FeedbackModal onClose={vi.fn()} />, { wrapper });
		await screen.findByText("Environment details");

		fireEvent.click(
			screen.getByRole("button", { name: "Copy environment JSON" }),
		);
		await waitFor(() =>
			expect(copyModule.copyToClipboard).toHaveBeenCalledWith(
				expect.stringContaining('"marimo": "1.2.3"'),
			),
		);
	});
});
