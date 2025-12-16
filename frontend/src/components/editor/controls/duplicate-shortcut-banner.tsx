/* Copyright 2024 Marimo. All rights reserved. */

import { AlertTriangleIcon } from "lucide-react";
import { KeyboardHotkeys } from "@/components/shortcuts/renderShortcut";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { DuplicateGroup } from "@/hooks/useDuplicateShortcuts";

interface DuplicateShortcutBannerProps {
  duplicates: DuplicateGroup[];
}

/**
 * Banner component that warns about duplicate keyboard shortcuts.
 * Displays a warning when multiple actions share the same key binding.
 */
export const DuplicateShortcutBanner: React.FC<
  DuplicateShortcutBannerProps
> = ({ duplicates }) => {
  // Don't render if no duplicates
  if (duplicates.length === 0) {
    return null;
  }

  return (
    <Alert variant="warning" className="mb-4">
      <AlertTriangleIcon className="h-4 w-4" />
      <AlertTitle>Duplicate shortcuts</AlertTitle>
      <AlertDescription>
        <p className="mb-2">
          Multiple actions are assigned to the same keyboard shortcut:
        </p>
        <ul className="space-y-2">
          {duplicates.map(({ key, actions }) => (
            <li key={key} className="text-xs">
              <div className="flex items-center gap-2 mb-1">
                <KeyboardHotkeys shortcut={key} />
                <span className="font-semibold">is used by:</span>
              </div>
              <ul className="ml-6 list-disc">
                {actions.map(({ action, name }) => (
                  <li key={action}>{name}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
};
