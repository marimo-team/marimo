/* Copyright 2026 Marimo. All rights reserved. */
import { useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { useRequestClient } from "@/core/network/requests";
import type { DependencyTreeNode } from "@/core/network/types";
import { prettyError } from "@/utils/errors";
import {
  showPackageRestartToast,
  showRemovePackageToast,
  showUpgradePackageToast,
} from "./toast-components";

/** Shared mutation lifecycle for package actions in both list and tree views. */
export function usePackageAction(
  action: "upgrade" | "remove",
  packageName: string,
  tags?: DependencyTreeNode["tags"],
) {
  const { addPackage, removePackage } = useRequestClient();
  const [loading, setLoading] = useState(false);
  const inFlight = useRef(false);
  const run = useEvent(async () => {
    if (inFlight.current) {
      return;
    }
    inFlight.current = true;
    setLoading(true);
    const showResult =
      action === "upgrade" ? showUpgradePackageToast : showRemovePackageToast;
    try {
      const group = tags?.find((tag) => tag.kind === "group")?.value;
      const request = { package: packageName, group };
      const response = await (action === "upgrade"
        ? addPackage({ ...request, upgrade: true })
        : removePackage(request));
      if (response.restartRequired) {
        showPackageRestartToast();
      } else if (response.success) {
        showResult(packageName);
      } else {
        showResult(packageName, response.error || "Package operation failed.");
      }
    } catch (error) {
      showResult(packageName, prettyError(error));
    } finally {
      inFlight.current = false;
      setLoading(false);
    }
  });
  return { loading, run };
}
