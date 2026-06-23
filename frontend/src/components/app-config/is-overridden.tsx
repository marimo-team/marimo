/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { get } from "lodash-es";
import { FolderCog2 } from "lucide-react";
import { useCallback } from "react";
import type {
  Control,
  ControllerRenderProps,
  FieldPath,
  FieldPathValue,
} from "react-hook-form";
import { FormField } from "@/components/ui/form";
import { Tooltip } from "@/components/ui/tooltip";
import { configOverridesAtom, useUserConfig } from "@/core/config/config";
import type { UserConfig } from "@/core/config/config-schema";
import { Kbd } from "../ui/kbd";

export interface ConfigOverride<T> {
  isOverridden: boolean;
  /**
   * The effective value: the project config value when overridden, otherwise
   * the user's own value.
   */
  value: T;
  userValue: unknown;
  projectValue: unknown;
}

function resolveOverride<T>({
  userConfig,
  overrides,
  name,
  value,
}: {
  userConfig: UserConfig;
  overrides: unknown;
  name: FieldPath<UserConfig>;
  value: T;
}): ConfigOverride<T> {
  const userValue = get(userConfig, name);
  const projectValue = get(overrides as UserConfig, name);
  const isOverridden = projectValue != null && userValue !== projectValue;
  return {
    isOverridden,
    userValue,
    projectValue,
    value: isOverridden ? (projectValue as T) : value,
  };
}

/**
 * Returns a function that resolves a form field against the project config
 * overrides (e.g. `pyproject.toml`).
 *
 * The returned function is a plain callback (not a hook), so it's safe to call
 * inside `FormField` render callbacks and loops.
 */
export function useConfigOverride(): <T>(
  name: FieldPath<UserConfig>,
  value: T,
) => ConfigOverride<T> {
  const [userConfig] = useUserConfig();
  const overrides = useAtomValue(configOverridesAtom);
  return useCallback(
    <T,>(name: FieldPath<UserConfig>, value: T): ConfigOverride<T> =>
      resolveOverride({ userConfig, overrides, name, value }),
    [userConfig, overrides],
  );
}

/**
 * A `FormField` that resolves the field against the project config overrides.
 */
export function OverriddenFormField<TName extends FieldPath<UserConfig>>({
  control,
  name,
  disabled,
  render,
}: {
  control: Control<UserConfig>;
  name: TName;
  disabled?: boolean;
  render: (args: {
    field: ControllerRenderProps<UserConfig, TName>;
    override: ConfigOverride<FieldPathValue<UserConfig, TName>>;
  }) => React.ReactElement;
}) {
  const getOverride = useConfigOverride();
  return (
    <FormField
      control={control}
      name={name}
      disabled={disabled}
      render={({ field }) =>
        render({
          field,
          // `field.value` is `FieldPathValue<UserConfig, TName>`, but the deep
          // conditional type doesn't reduce for the compiler, so we narrow it.
          override: getOverride(name, field.value) as ConfigOverride<
            FieldPathValue<UserConfig, TName>
          >,
        })
      }
    />
  );
}

/**
 * Shared explanation shown in override tooltips, so the wording stays
 * consistent across the badge and the disabled-wrapper.
 */
const OverriddenExplanation = () => (
  <>
    <p>
      This setting is overridden by the{" "}
      <Kbd className="inline mx-px">pyproject.toml</Kbd> config.
    </p>
    <p>
      To change it, edit the project config{" "}
      <Kbd className="inline mx-px">pyproject.toml</Kbd> directly.
    </p>
  </>
);

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
  const { isOverridden } = useConfigOverride()(name, undefined);
  return isOverridden ? (
    <Tooltip
      delayDuration={200}
      content={
        <div className="flex flex-col gap-2">
          <OverriddenExplanation />
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
  override,
}: {
  override: ConfigOverride<unknown>;
}) => {
  if (!override.isOverridden) {
    return null;
  }

  return (
    <Tooltip
      content={
        <div className="flex flex-col gap-2">
          <OverriddenExplanation />
          <p>
            User value: <strong>{String(override.userValue)}</strong>
            <br />
            Project value: <strong>{String(override.projectValue)}</strong>
          </p>
        </div>
      }
    >
      <span className="text-(--amber-12) text-xs flex items-center gap-1 border rounded px-2 py-1 bg-(--amber-2) border-(--amber-6) ml-1">
        <FolderCog2 className="w-3 h-3" />
        Overridden by pyproject.toml
      </span>
    </Tooltip>
  );
};
