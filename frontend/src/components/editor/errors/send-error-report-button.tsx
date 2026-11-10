/* Copyright 2026 Marimo. All rights reserved. */

import { SendToAgentButton } from "../actions/send-to-agent-button";

export function SendErrorReportButton({
  getContent,
}: {
  getContent: () => unknown;
}) {
  return (
    <SendToAgentButton getContent={getContent}>
      Send error to agent
    </SendToAgentButton>
  );
}
