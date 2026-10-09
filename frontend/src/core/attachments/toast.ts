/* Copyright 2026 Marimo. All rights reserved. */

import { toast } from "@/components/ui/use-toast";

export function agentToast(
  options: Pick<Parameters<typeof toast>[0], "title" | "variant">,
) {
  const duration = options.variant === "danger" ? 5000 : 3000;
  const { dismiss } = toast({ ...options, duration });
  // Agent notices must also expire while the user focuses the agent terminal.
  window.setTimeout(dismiss, duration);
}
