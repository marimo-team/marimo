/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { get } from "lodash-es";
import { FolderCog2 } from "lucide-react";
import type { FieldPath } from "react-hook-form";
import { Tooltip } from "@/components/ui/tooltip";
import { configOverridesAtom, useUserConfig } from "@/core/config/config";
import type { UserConfig } from "@/core/config/config-schema";
import { Kbd } from "../ui/kbd";

/**
 * Hook to determine if a user config value is overridden by project config.
 * Returns { isOverridden, currentValue, overriddenValue }
 */
function useIsConfigOverridden(
  userConfig: UserConfig,
  name: FieldPath<UserConfig>,
): {
  isOverridden: boolean;
  currentValue: unknown;
  overriddenValue: unknown;
} {
  const currentValue = get(userConfig, name);
  const overrides = useAtomValue(configOverridesAtom);
  const overriddenValue = get(overrides as UserConfig, name);

  const isOverridden =
    overriddenValue != null && currentValue !== overriddenValue;

  return { isOverridden, currentValue, overriddenValue };
}

/**
 * Wraps a component and shows a tooltip if the user config is overridden by the
 * project config.
 */
export const DisableIfOverridden = ({
  name,
  children,
}: {
  name: FieldPath<UserConfig>;
  children: React.ReactNode;
}) => {
  const [userConfig] = useUserConfig();
  const { isOverridden } = useIsConfigOverridden(userConfig, name);
  return isOverridden ? (
    <Tooltip
      delayDuration={200}
      content={
        <div className="flex flex-col gap-2">
          <p>
            This setting is overridden by the{" "}
            <Kbd className="inline mx-px">pyproject.toml</Kbd> config.
          </p>
          <p>
            To change it, edit the project config{" "}
            <Kbd className="inline mx-px">pyproject.toml</Kbd>
            directly.
          </p>
        </div>
      }
    >
      <div className="text-muted-foreground opacity-80 cursor-not-allowed *:pointer-events-none">
        {children}
      </div>
    </Tooltip>
  ) : (
    children
  );
};

export const IsOverridden = ({
  userConfig,
  name,
}: {
  userConfig: UserConfig;
  name: FieldPath<UserConfig>;
}) => {
  const { isOverridden, currentValue, overriddenValue } = useIsConfigOverridden(
    userConfig,
    name,
  );

  if (!isOverridden) {
    return null;
  }

  return (
    <Tooltip
      content={
        <>
          <span>
            This setting is overridden by{" "}
            <Kbd className="inline">pyproject.toml</Kbd>.
          </span>
          <br />
          <span>
            Edit the <Kbd className="inline">pyproject.toml</Kbd> file directly
            to change this setting.
          </span>
          <br />
          <span>
            User value: <strong>{String(currentValue)}</strong>
          </span>
          <br />
          <span>
            Project value: <strong>{String(overriddenValue)}</strong>
          </span>
        </>
      }
    >
      <span className="text-(--amber-12) text-xs flex items-center gap-1 border rounded px-2 py-1 bg-(--amber-2) border-(--amber-6) ml-1">
        <FolderCog2 className="w-3 h-3" />
        Overridden by pyproject.toml [{String(overriddenValue)}]
      </span>
    </Tooltip>
  );
};
