/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { get } from "lodash-es";
import type { FieldPath } from "react-hook-form";
import { Tooltip } from "@/components/ui/tooltip";
import { configOverridesAtom, useUserConfig } from "@/core/config/config";
import type { UserConfig } from "@/core/config/config-schema";
import { Kbd } from "../ui/kbd";

/**
 * Hook to determine if a user config value is overridden by project config.
 * Returns { isOverridden, currentValue, overriddenValue }
 */
export function useIsConfigOverridden(
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
            <Kbd className="inline mx-[1px]">pyproject.toml</Kbd> config.
          </p>
          <p>
            To change it, edit the project config{" "}
            <Kbd className="inline mx-[1px]">pyproject.toml</Kbd>
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
