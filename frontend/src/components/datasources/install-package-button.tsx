/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Button } from "@/components/ui/button";
import { store } from "@/core/state/jotai";
import { chromeAtom } from "@/components/editor/chrome/state";
import { PACKAGES_INPUT_ID } from "@/components/editor/chrome/panels/constants";

interface InstallPackageButtonProps {
  packages: string[] | undefined;
}

/**
 * Button to install missing packages
 * Opens the packages panel and focuses the input
 */
export const InstallPackageButton: React.FC<InstallPackageButtonProps> = ({
  packages,
}) => {
  if (!packages || packages.length === 0) {
    return null;
  }

  const handleClick = () => {
    // Open the packages panel
    store.set(chromeAtom, (prev) => ({
      ...prev,
      isSidebarOpen: true,
      selectedPanel: "packages",
    }));

    // Focus the packages input and set the value
    requestAnimationFrame(() => {
      const input = document.getElementById(
        PACKAGES_INPUT_ID,
      ) as HTMLInputElement | null;
      if (input) {
        input.focus();
        input.value = packages.join(", ");
        // Trigger a change event to update the input value
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  };

  return (
    <Button variant="outline" size="xs" onClick={handleClick} className="ml-2">
      Install {packages.join(", ")}
    </Button>
  );
};
