/* Copyright 2026 Marimo. All rights reserved. */

import { Slot as SlotPrimitive } from "radix-ui";

const Slot = SlotPrimitive.Slot;

import { useAtomValue } from "jotai";
import { CopyIcon, ExternalLinkIcon, TriangleAlertIcon } from "lucide-react";
import React, { type PropsWithChildren, useMemo } from "react";
import { useImperativeModal } from "@/components/modal/ImperativeModal";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import {
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "@/components/ui/use-toast";
import { notebookAtom } from "@/core/cells/cells";
import { Constants } from "@/core/constants";
import {
	buildIssueDetails,
	createPartialEnvironment,
	type EnvironmentDiagnostics,
	enrichEnvironment,
} from "@/core/diagnostics/issue-details";
import {
	formatCellError,
	getCellErrorEntries,
} from "@/core/errors/error-entries";
import { getMarimoVersion } from "@/core/meta/globals";
import { useRequestClient } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { useAsyncData } from "@/hooks/useAsyncData";
import { copyToClipboard } from "@/utils/copy";

export const FeedbackButton: React.FC<PropsWithChildren> = ({ children }) => {
	const { openModal, closeModal } = useImperativeModal();

	return (
		<Slot onClick={() => openModal(<FeedbackModal onClose={closeModal} />)}>
			{children}
		</Slot>
	);
};

export const FeedbackModal: React.FC<{
	onClose: () => void;
}> = () => {
	const { getEnvironmentInfo } = useRequestClient();
	const environmentRequest = useAsyncData(
		async () => getEnvironmentInfo(),
		[getEnvironmentInfo],
	);

	const notebook = useAtomValue(notebookAtom);
	// biome-ignore lint/correctness/useExhaustiveDependencies: recompute when the notebook changes
	const errors = useMemo(() => getCellErrorEntries(store), [notebook]);

	const environment: EnvironmentDiagnostics | undefined =
		environmentRequest.data
			? enrichEnvironment(environmentRequest.data, navigator.userAgent)
			: environmentRequest.status === "error"
				? createPartialEnvironment(
						getMarimoVersion(),
						navigator.userAgent,
						navigator.language,
						"Server environment information unavailable",
					)
				: undefined;

	const copyEnvironment = async () => {
		if (!environment) {
			return;
		}
		await copyToClipboard(JSON.stringify(environment, null, 2));
		toast({ title: "Environment details copied" });
	};

	const copyIssueDetails = async () => {
		if (!environment) {
			return;
		}
		await copyToClipboard(buildIssueDetails({ environment, errors }));
		toast({
			title:
				environmentRequest.status === "error"
					? "Partial issue details copied"
					: "Issue details copied",
		});
	};

	return (
		<DialogContent className="w-[540px] max-w-[90vw]">
			<DialogHeader>
				<DialogTitle>Report an issue</DialogTitle>
				<DialogDescription>
					Copy your environment and any current errors to include in a GitHub
					bug report. Nothing is uploaded automatically; review the details
					before posting.
				</DialogDescription>
			</DialogHeader>

			<div className="flex flex-col gap-4 max-h-[60vh] overflow-y-auto">
				<div className="flex flex-wrap gap-2">
					<Button
						type="button"
						variant="default"
						disabled={!environment}
						onClick={copyIssueDetails}
					>
						Copy issue details
					</Button>
					<Button type="button" variant="outline" asChild={true}>
						<a href={Constants.bugReportUrl} target="_blank" rel="noreferrer">
							<ExternalLinkIcon className="w-4 h-4 mr-2" />
							Open GitHub issue
						</a>
					</Button>
				</div>

				{environmentRequest.status === "pending" && (
					<div className="flex flex-col gap-2">
						<span className="text-sm text-muted-foreground">
							Loading environment details…
						</span>
						<Skeleton className="h-4 w-full" />
						<Skeleton className="h-4 w-3/4" />
						<Skeleton className="h-4 w-1/2" />
					</div>
				)}

				{environmentRequest.status === "error" && (
					<div className="flex items-center gap-2 text-sm">
						<TriangleAlertIcon className="w-4 h-4 text-(--yellow-11) shrink-0" />
						<span>Server environment information unavailable</span>
						<Button
							type="button"
							variant="link"
							size="xs"
							onClick={() => environmentRequest.refetch()}
						>
							Retry
						</Button>
					</div>
				)}

				{environment && (
					<Accordion type="single" collapsible={true}>
						<AccordionItem value="environment">
							<div className="flex items-center justify-between">
								<AccordionTrigger className="flex-1 py-2 text-sm">
									Environment details
								</AccordionTrigger>
								<Button
									type="button"
									variant="text"
									size="icon"
									aria-label="Copy environment JSON"
									onClick={copyEnvironment}
								>
									<CopyIcon className="w-3.5 h-3.5" />
								</Button>
							</div>
							<AccordionContent forceMount={true}>
								<pre className="text-xs bg-muted rounded p-2 overflow-x-auto whitespace-pre-wrap">
									{JSON.stringify(environment, null, 2)}
								</pre>
							</AccordionContent>
						</AccordionItem>

						{errors.length > 0 && (
							<AccordionItem value="errors">
								<AccordionTrigger className="py-2 text-sm">
									Current errors
								</AccordionTrigger>
								<AccordionContent forceMount={true}>
									<pre className="text-xs bg-muted rounded p-2 overflow-x-auto whitespace-pre-wrap">
										{errors.map(formatCellError).join("\n\n---\n\n")}
									</pre>
								</AccordionContent>
							</AccordionItem>
						)}
					</Accordion>
				)}

				{environment && errors.length === 0 && (
					<span className="text-sm text-muted-foreground">
						No current errors detected.
					</span>
				)}

				<div className="border-t pt-3">
					<p className="text-sm text-muted-foreground">
						Other feedback? Take our{" "}
						<a
							href={Constants.feedbackForm}
							target="_blank"
							rel="noreferrer"
							className="underline"
						>
							two-minute survey
						</a>{" "}
						or chat with us on{" "}
						<a
							href={Constants.discordLink}
							target="_blank"
							rel="noreferrer"
							className="underline"
						>
							Discord
						</a>
						.
					</p>
				</div>
			</div>
		</DialogContent>
	);
};
