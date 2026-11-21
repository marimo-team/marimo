/* Copyright 2026 Marimo. All rights reserved. */

import type { CellDiagnostic } from "@marimo-team/client/protocol";
import { HelpCircleIcon, SquareFunctionIcon } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";

const LEARN_MORE = "https://links.marimo.app/reusable-definitions";

/** Whether a lone function or class is saved at module scope, and why not. */
export const ReusableDefinitionBadge = ({
  finding,
}: {
  finding: CellDiagnostic;
}) => {
  const reusable = finding.kind === "reusable-definition";
  const Icon = reusable ? SquareFunctionIcon : HelpCircleIcon;
  return (
    <div className="py-1 px-2 flex items-center justify-end gap-2 last:rounded-b">
      {reusable && (
        <a
          href={LEARN_MORE}
          target="_blank"
          className="hover:underline text-muted-foreground text-xs font-bold"
          rel="noreferrer"
        >
          reusable
        </a>
      )}
      <Tooltip
        content={
          <span className="max-w-16 text-xs">
            {reusable ? (
              finding.message
            ) : (
              <>
                This definition can't be reused in other Python modules:
                <br />
                <br />
                <pre>{finding.message}</pre>
                <br />
                Click this icon to learn more.
              </>
            )}
          </span>
        }
      >
        <a
          href={LEARN_MORE}
          target="_blank"
          rel="noreferrer"
          aria-label="Learn about reusable definitions"
        >
          <Icon
            size={16}
            strokeWidth={1.5}
            className="rounded-lg text-muted-foreground"
          />
        </a>
      </Tooltip>
    </div>
  );
};
