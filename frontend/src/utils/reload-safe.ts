/* Copyright 2024 Marimo. All rights reserved. */
import { toast } from "@/components/ui/use-toast";
import { Logger } from "./Logger";

export function reloadSafe() {
  try {
    globalThis.location.reload();
  } catch (error) {
    Logger.error("Failed to reload page", error);
    toast({
      title: "Failed to reload page",
      description: "Please refresh the page manually.",
    });
  }
}
