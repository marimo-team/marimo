/* Copyright 2026 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import {
  AlertTriangleIcon,
  BrainIcon,
  CpuIcon,
  EditIcon,
  FlaskConicalIcon,
  FolderCog2,
  LayersIcon,
  MonitorIcon,
} from "lucide-react";
import React, { useId, useRef } from "react";
import { useLocale } from "react-aria";
import type { FieldValues } from "react-hook-form";
import { useForm } from "react-hook-form";
import type z from "zod";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Kbd } from "@/components/ui/kbd";
import { NativeSelect } from "@/components/ui/native-select";
import { NumberField } from "@/components/ui/number-field";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { KEYMAP_PRESETS } from "@/core/codemirror/keymaps/keymaps";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { useUserConfig } from "@/core/config/config";
import {
  PackageManagerNames,
  type UserConfig,
  UserConfigSchema,
} from "@/core/config/config-schema";
import { getAppWidths } from "@/core/config/widths";
import { marimoVersionAtom } from "@/core/meta/state";
import { viewStateAtom } from "@/core/mode";
import { useRequestClient } from "@/core/network/requests";
import { isWasm } from "@/core/wasm/utils";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { Banner } from "@/plugins/impl/common/error-banner";
import { THEMES } from "@/theme/useTheme";
import { arrayToggle } from "@/utils/arrays";
import { cn } from "@/utils/cn";
import { keyboardShortcutsAtom } from "../editor/controls/keyboard-shortcuts";
import { Badge } from "../ui/badge";
import { ExternalLink } from "../ui/links";
import { Tooltip } from "../ui/tooltip";
import { AiConfig } from "./ai-config";
import { formItemClasses, SettingGroup } from "./common";
import { DataForm } from "./data-form";
import { IsOverridden } from "./is-overridden";
import { OptionalFeatures } from "./optional-features";

/**
 * Extract only the values that have been modified (dirty) from form state.
 * This prevents sending unchanged fields that could overwrite backend values.
 */
export function getDirtyValues<T extends FieldValues>(
  values: T,
  dirtyFields: Partial<Record<keyof T, unknown>>,
): Partial<T> {
  const result: Partial<T> = {};
  for (const key of Object.keys(dirtyFields) as (keyof T)[]) {
    const dirty = dirtyFields[key];
    if (dirty === true) {
      result[key] = values[key];
    } else if (typeof dirty === "object" && dirty !== null) {
      // Nested object - recurse
      const nested = getDirtyValues(
        values[key] as FieldValues,
        dirty as Partial<Record<string, unknown>>,
      );
      if (Object.keys(nested).length > 0) {
        result[key] = nested as T[keyof T];
      }
    }
  }
  return result;
}

const categories = [
  {
    id: "editor",
    label: "Editor",
    Icon: EditIcon,
    className: "bg-(--blue-4)",
  },
  {
    id: "display",
    label: "Display",
    Icon: MonitorIcon,
    className: "bg-(--grass-4)",
  },
  {
    id: "packageManagementAndData",
    label: "Packages & Data",
    Icon: LayersIcon,
    className: "bg-(--red-4)",
  },
  {
    id: "runtime",
    label: "Runtime",
    Icon: CpuIcon,
    className: "bg-(--amber-4)",
  },
  {
    id: "ai",
    label: "AI",
    Icon: BrainIcon,
    className: "bg-[linear-gradient(45deg,var(--purple-5),var(--cyan-5))]",
  },
  {
    id: "optionalDeps",
    label: "Optional Dependencies",
    Icon: FolderCog2,
    className: "bg-(--orange-4)",
  },
  {
    id: "labs",
    label: "Labs",
    Icon: FlaskConicalIcon,
    className: "bg-(--slate-4)",
  },
] as const;

export type SettingCategoryId = (typeof categories)[number]["id"];

export const activeUserConfigCategoryAtom = atom<SettingCategoryId>(
  categories[0].id,
);

const FORM_DEBOUNCE = 100; // ms;
const LOCALE_SYSTEM_VALUE = "__system__";

export const UserConfigForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();
  const formElement = useRef<HTMLFormElement>(null);
  const setKeyboardShortcutsOpen = useSetAtom(keyboardShortcutsAtom);
  const [activeCategory, setActiveCategory] = useAtom(
    activeUserConfigCategoryAtom,
  );

  let capabilities = useAtomValue(capabilitiesAtom);
  const isHome = useAtomValue(viewStateAtom).mode === "home";
  // The home page does not fetch kernel capabilities, so we just turn them all on
  if (isHome) {
    capabilities = {
      terminal: true,
      pylsp: true,
      ty: true,
      basedpyright: true,
    };
  }

  const marimoVersion = useAtomValue(marimoVersionAtom);
  const { locale } = useLocale();
  const { saveUserConfig } = useRequestClient();

  // Create form
  const form = useForm({
    resolver: zodResolver(
      UserConfigSchema as unknown as z.ZodType<unknown, UserConfig>,
    ),
    defaultValues: config,
  });

  const onSubmitNotDebounced = async (values: UserConfig) => {
    // Only send values that were actually changed to avoid
    // overwriting backend values the form doesn't manage
    const dirtyValues = getDirtyValues(values, form.formState.dirtyFields);
    if (Object.keys(dirtyValues).length === 0) {
      return; // Nothing changed
    }
    await saveUserConfig({ config: dirtyValues }).then(() => {
      // Update local state with form values
      setConfig((prev) => ({ ...prev, ...values }));
    });
  };
  const onSubmit = useDebouncedCallback(onSubmitNotDebounced, FORM_DEBOUNCE);

  const isWasmRuntime = isWasm();
  const htmlCheckboxId = useId();
  const ipynbCheckboxId = useId();

  const renderBody = () => {
    switch (activeCategory) {
      case "editor":
        return (
          <>
            <SettingGroup title="Autosave">
              <FormField
                control={form.control}
                name="save.autosave"
                render={({ field }) => (
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      Autosave enabled
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="autosave-checkbox"
                        checked={field.value === "after_delay"}
                        disabled={field.disabled}
                        onCheckedChange={(checked) => {
                          field.onChange(checked ? "after_delay" : "off");
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                    <IsOverridden userConfig={config} name="save.autosave" />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="save.autosave_delay"
                render={({ field }) => (
                  <FormItem className={formItemClasses}>
                    <FormLabel>Autosave delay (seconds)</FormLabel>
                    <FormControl>
                      <NumberField
                        aria-label="Autosave delay"
                        data-testid="autosave-delay-input"
                        className="m-0 w-24"
                        isDisabled={
                          form.getValues("save.autosave") !== "after_delay"
                        }
                        {...field}
                        value={field.value / 1000}
                        minValue={1}
                        onChange={(value) => {
                          field.onChange(value * 1000);
                          if (!Number.isNaN(value)) {
                            onSubmit(form.getValues());
                          }
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="save.autosave_delay"
                    />
                  </FormItem>
                )}
              />
              {/* auto_download is a runtime setting in the backend, but it makes
               * more sense as an autosave setting. */}
              <FormField
                control={form.control}
                name="runtime.default_auto_download"
                render={({ field }) => (
                  <div className="flex flex-col gap-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Save cell outputs as</FormLabel>
                      <FormControl>
                        <div className="flex gap-4">
                          <div className="flex items-center space-x-2">
                            <Checkbox
                              id={htmlCheckboxId}
                              checked={
                                Array.isArray(field.value) &&
                                field.value.includes("html")
                              }
                              onCheckedChange={() => {
                                const currentValue = Array.isArray(field.value)
                                  ? field.value
                                  : [];
                                field.onChange(
                                  arrayToggle(currentValue, "html"),
                                );
                              }}
                            />
                            <FormLabel htmlFor={htmlCheckboxId}>HTML</FormLabel>
                          </div>
                          <div className="flex items-center space-x-2">
                            <Checkbox
                              id={ipynbCheckboxId}
                              checked={
                                Array.isArray(field.value) &&
                                field.value.includes("ipynb")
                              }
                              onCheckedChange={() => {
                                const currentValue = Array.isArray(field.value)
                                  ? field.value
                                  : [];
                                field.onChange(
                                  arrayToggle(currentValue, "ipynb"),
                                );
                              }}
                            />
                            <FormLabel htmlFor={ipynbCheckboxId}>
                              IPYNB
                            </FormLabel>
                          </div>
                        </div>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="runtime.default_auto_download"
                      />
                    </FormItem>
                    <FormDescription>
                      When enabled, marimo will periodically save notebooks in
                      your selected formats (HTML, IPYNB) to a folder named{" "}
                      <Kbd className="inline">__marimo__</Kbd> next to your
                      notebook file.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
            <SettingGroup title="Formatting">
              <FormField
                control={form.control}
                name="save.format_on_save"
                render={({ field }) => (
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      Format on save
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="format-on-save-checkbox"
                        checked={field.value}
                        disabled={field.disabled}
                        onCheckedChange={(checked) => {
                          field.onChange(checked);
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="save.format_on_save"
                    />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="formatting.line_length"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Line length</FormLabel>
                      <FormControl>
                        <NumberField
                          aria-label="Line length"
                          data-testid="line-length-input"
                          className="m-0 w-24"
                          {...field}
                          value={field.value}
                          minValue={1}
                          maxValue={1000}
                          onChange={(value) => {
                            // Ignore NaN
                            field.onChange(value);
                            if (!Number.isNaN(value)) {
                              onSubmit(form.getValues());
                            }
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="formatting.line_length"
                      />
                    </FormItem>

                    <FormDescription>
                      Maximum line length when formatting code.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
            <SettingGroup title="Autocomplete">
              <FormField
                control={form.control}
                name="completion.activate_on_typing"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel className="font-normal">
                        Autocomplete
                      </FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="autocomplete-checkbox"
                          checked={field.value}
                          disabled={field.disabled}
                          onCheckedChange={(checked) => {
                            field.onChange(Boolean(checked));
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="completion.activate_on_typing"
                      />
                    </FormItem>
                    <FormDescription>
                      When unchecked, code completion is still available through
                      a hotkey.
                    </FormDescription>

                    <div>
                      <Button
                        variant="link"
                        className="mb-0 px-0"
                        type="button"
                        onClick={(evt) => {
                          evt.preventDefault();
                          evt.stopPropagation();
                          setActiveCategory("ai");
                        }}
                      >
                        Edit AI autocomplete
                      </Button>
                    </div>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="completion.signature_hint_on_typing"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel className="font-normal">
                        Signature hints
                      </FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="signature-hint-on-type-checkbox"
                          checked={field.value ?? false}
                          disabled={field.disabled}
                          onCheckedChange={(checked) => {
                            field.onChange(Boolean(checked));
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="completion.signature_hint_on_typing"
                      />
                    </FormItem>
                    <FormDescription>
                      Display signature hints while typing within function
                      calls.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
            <SettingGroup title="Language Servers">
              <FormDescription>
                See the{" "}
                <ExternalLink href="https://docs.marimo.io/guides/editor_features/language_server/">
                  docs
                </ExternalLink>{" "}
                for more information about language server support.
              </FormDescription>
              <FormDescription>
                <strong>Note:</strong> When using multiple language servers,
                different features may conflict.
              </FormDescription>

              <FormField
                control={form.control}
                name="language_servers.pylsp.enabled"
                render={({ field }) => (
                  <div className="flex flex-col gap-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>
                        <Badge variant="defaultOutline" className="mr-2">
                          Beta
                        </Badge>
                        Python Language Server (
                        <ExternalLink href="https://github.com/python-lsp/python-lsp-server">
                          docs
                        </ExternalLink>
                        )
                      </FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="pylsp-checkbox"
                          checked={field.value}
                          disabled={field.disabled}
                          onCheckedChange={(checked) => {
                            field.onChange(Boolean(checked));
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="language_servers.pylsp.enabled"
                      />
                    </FormItem>
                    {field.value && !capabilities.pylsp && (
                      <Banner kind="danger">
                        The Python Language Server is not available in your
                        current environment. Please install{" "}
                        <Kbd className="inline">python-lsp-server</Kbd> in your
                        environment.
                      </Banner>
                    )}
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="language_servers.basedpyright.enabled"
                render={({ field }) => (
                  <div className="flex flex-col gap-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>
                        <Badge variant="defaultOutline" className="mr-2">
                          Beta
                        </Badge>
                        basedpyright (
                        <ExternalLink href="https://github.com/DetachHead/basedpyright">
                          docs
                        </ExternalLink>
                        )
                      </FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="basedpyright-checkbox"
                          checked={field.value}
                          disabled={field.disabled}
                          onCheckedChange={(checked) => {
                            field.onChange(Boolean(checked));
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="language_servers.basedpyright.enabled"
                      />
                    </FormItem>
                    {field.value && !capabilities.basedpyright && (
                      <Banner kind="danger">
                        basedpyright is not available in your current
                        environment. Please install{" "}
                        <Kbd className="inline">basedpyright</Kbd> in your
                        environment.
                      </Banner>
                    )}
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="language_servers.ty.enabled"
                render={({ field }) => (
                  <div className="flex flex-col gap-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>
                        <Badge variant="defaultOutline" className="mr-2">
                          Beta
                        </Badge>
                        ty (
                        <ExternalLink href="https://github.com/astral-sh/ty">
                          docs
                        </ExternalLink>
                        )
                      </FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="ty-checkbox"
                          checked={field.value}
                          disabled={field.disabled}
                          onCheckedChange={(checked) => {
                            field.onChange(Boolean(checked));
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="language_servers.ty.enabled"
                      />
                    </FormItem>
                    {field.value && !capabilities.ty && (
                      <Banner kind="danger">
                        ty is not available in your current environment. Please
                        install <Kbd className="inline">ty</Kbd> in your
                        environment.
                      </Banner>
                    )}
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="diagnostics.enabled"
                render={({ field }) => (
                  <FormItem className={formItemClasses}>
                    <FormLabel>
                      <Badge variant="defaultOutline" className="mr-2">
                        Beta
                      </Badge>
                      Diagnostics
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="diagnostics-checkbox"
                        checked={field.value}
                        disabled={field.disabled}
                        onCheckedChange={(checked) => {
                          field.onChange(Boolean(checked));
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="diagnostics.enabled"
                    />
                  </FormItem>
                )}
              />
            </SettingGroup>

            <SettingGroup title="Keymap">
              <FormField
                control={form.control}
                name="keymap.preset"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Keymap</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="keymap-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={field.value}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {KEYMAP_PRESETS.map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden userConfig={config} name="keymap.preset" />
                    </FormItem>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="keymap.destructive_delete"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel className="font-normal">
                        Destructive delete
                      </FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="destructive-delete-checkbox"
                          checked={field.value}
                          disabled={field.disabled}
                          onCheckedChange={(checked) => {
                            field.onChange(Boolean(checked));
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="keymap.destructive_delete"
                      />
                    </FormItem>
                    <FormDescription className="flex items-center gap-1">
                      Allow deleting non-empty cells
                      <Tooltip
                        content={
                          <div className="max-w-xs">
                            <strong>Use with caution:</strong> Deleting cells
                            with code can lose work and computed results since
                            variables are removed from memory.
                          </div>
                        }
                      >
                        <AlertTriangleIcon className="w-3 h-3 text-(--amber-11)" />
                      </Tooltip>
                    </FormDescription>

                    <div>
                      <Button
                        variant="link"
                        className="mb-0 px-0"
                        type="button"
                        onClick={(evt) => {
                          evt.preventDefault();
                          evt.stopPropagation();
                          setKeyboardShortcutsOpen(true);
                        }}
                      >
                        Edit Keyboard Shortcuts
                      </Button>
                    </div>
                  </div>
                )}
              />
            </SettingGroup>
          </>
        );
      case "display":
        return (
          <>
            <SettingGroup title="Display">
              <FormField
                control={form.control}
                name="display.default_width"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Default width</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="user-config-width-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={field.value}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {getAppWidths().map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="display.default_width"
                      />
                    </FormItem>

                    <FormDescription>
                      The default app width for new notebooks; overridden by
                      "width" in the application config.
                    </FormDescription>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="display.theme"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Theme</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="theme-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={field.value}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {THEMES.map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden userConfig={config} name="display.theme" />
                    </FormItem>

                    <FormDescription>
                      This theme will be applied to the user's configuration; it
                      does not affect theme when sharing the notebook.
                    </FormDescription>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="display.code_editor_font_size"
                render={({ field }) => (
                  <FormItem className={formItemClasses}>
                    <FormLabel>Code editor font size (px)</FormLabel>
                    <FormControl>
                      <span className="inline-flex mr-2">
                        <NumberField
                          aria-label="Code editor font size"
                          data-testid="code-editor-font-size-input"
                          className="m-0 w-24"
                          {...field}
                          value={field.value}
                          minValue={8}
                          maxValue={32}
                          onChange={(value) => {
                            field.onChange(value);
                            onSubmit(form.getValues());
                          }}
                        />
                      </span>
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="display.code_editor_font_size"
                    />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="display.locale"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Locale</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="locale-select"
                          onChange={(e) => {
                            if (e.target.value === LOCALE_SYSTEM_VALUE) {
                              field.onChange(undefined);
                            } else {
                              field.onChange(e.target.value);
                            }
                          }}
                          value={field.value || LOCALE_SYSTEM_VALUE}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          <option value={LOCALE_SYSTEM_VALUE}>System</option>
                          {navigator.languages.map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden userConfig={config} name="display.locale" />
                    </FormItem>

                    <FormDescription>
                      The locale to use for the notebook. If your desired locale
                      is not listed, you can change it manually via{" "}
                      <Kbd className="inline">marimo config show</Kbd>.
                    </FormDescription>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="display.reference_highlighting"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Reference highlighting</FormLabel>
                      <FormControl>
                        <Checkbox
                          data-testid="reference-highlighting-checkbox"
                          checked={field.value}
                          onCheckedChange={field.onChange}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="display.reference_highlighting"
                      />
                    </FormItem>

                    <FormDescription>
                      Visually emphasizes variables in a cell that are defined
                      elsewhere in the notebook.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
            <SettingGroup title="Outputs">
              <FormField
                control={form.control}
                name="display.cell_output"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Cell output area</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="cell-output-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={field.value}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {["above", "below"].map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="display.cell_output"
                      />
                    </FormItem>

                    <FormDescription>
                      Where to display cell's output.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
          </>
        );
      case "packageManagementAndData":
        return (
          <>
            <SettingGroup title="Package Management">
              <FormField
                control={form.control}
                disabled={isWasmRuntime}
                name="package_management.manager"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Manager</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="package-manager-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={field.value}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {PackageManagerNames.map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="package_management.manager"
                      />
                    </FormItem>

                    <FormDescription>
                      When marimo comes across a module that is not installed,
                      you will be prompted to install it using your preferred
                      package manager. Learn more in the{" "}
                      <ExternalLink href="https://docs.marimo.io/guides/editor_features/package_management.html">
                        docs
                      </ExternalLink>
                      .
                      <br />
                      <br />
                      Running marimo in a{" "}
                      <ExternalLink href="https://docs.marimo.io/guides/editor_features/package_management.html#running-marimo-in-a-sandbox-environment-uv-only">
                        sandboxed environment
                      </ExternalLink>{" "}
                      is only supported by <Kbd className="inline">uv</Kbd>
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
            <SettingGroup title="Data">
              <DataForm form={form} config={config} onSubmit={onSubmit} />
            </SettingGroup>
          </>
        );
      case "runtime":
        return (
          <SettingGroup title="Runtime configuration">
            <FormField
              control={form.control}
              name="runtime.auto_instantiate"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      Autorun on startup
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="auto-instantiate-checkbox"
                        disabled={field.disabled}
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="runtime.auto_instantiate"
                    />
                  </FormItem>

                  <FormDescription>
                    Whether to automatically run all cells on startup.
                  </FormDescription>
                </div>
              )}
            />
            <FormField
              control={form.control}
              name="runtime.on_cell_change"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      On cell change
                    </FormLabel>
                    <FormControl>
                      <NativeSelect
                        data-testid="on-cell-change-select"
                        onChange={(e) => field.onChange(e.target.value)}
                        value={field.value}
                        className="inline-flex mr-2"
                      >
                        {["lazy", "autorun"].map((option) => (
                          <option value={option} key={option}>
                            {option}
                          </option>
                        ))}
                      </NativeSelect>
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="runtime.on_cell_change"
                    />
                  </FormItem>
                  <FormDescription>
                    Whether marimo should automatically run cells or just mark
                    them as stale. If "autorun", marimo will automatically run
                    affected cells when a cell is run or a UI element is
                    interacted with; if "lazy", marimo will mark affected cells
                    as stale but won't re-run them.
                  </FormDescription>
                </div>
              )}
            />
            <FormField
              control={form.control}
              name="runtime.auto_reload"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      On module change
                    </FormLabel>
                    <FormControl>
                      <NativeSelect
                        data-testid="auto-reload-select"
                        onChange={(e) => field.onChange(e.target.value)}
                        value={field.value}
                        disabled={isWasmRuntime}
                        className="inline-flex mr-2"
                      >
                        {["off", "lazy", "autorun"].map((option) => (
                          <option value={option} key={option}>
                            {option}
                          </option>
                        ))}
                      </NativeSelect>
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="runtime.auto_reload"
                    />
                  </FormItem>
                  <FormDescription>
                    Whether marimo should automatically reload modules before
                    executing cells. If "lazy", marimo will mark cells affected
                    by module modifications as stale; if "autorun", affected
                    cells will be automatically re-run.
                  </FormDescription>
                </div>
              )}
            />

            <FormField
              control={form.control}
              name="runtime.reactive_tests"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      Autorun Unit Tests
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="reactive-test-checkbox"
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                  <IsOverridden
                    userConfig={config}
                    name="runtime.reactive_tests"
                  />
                  <FormMessage />
                  <FormDescription>
                    Enable reactive pytest tests in notebook. When a cell
                    contains only test functions (test_*) and classes (Test_*),
                    marimo will automatically run them with pytest (requires
                    notebook restart).
                  </FormDescription>{" "}
                </div>
              )}
            />

            <FormDescription>
              Learn more in the{" "}
              <ExternalLink href="https://docs.marimo.io/guides/reactivity/#configuring-how-marimo-runs-cells">
                docs
              </ExternalLink>
              .
            </FormDescription>
          </SettingGroup>
        );
      case "ai":
        return <AiConfig form={form} config={config} onSubmit={onSubmit} />;
      case "optionalDeps":
        return <OptionalFeatures />;
      case "labs":
        return (
          <SettingGroup title="Experimental Features">
            <p className="text-sm text-muted-secondary mb-4">
              ⚠️ These features are experimental and may require restarting your
              notebook to take effect.
            </p>

            <FormField
              control={form.control}
              name="experimental.rtc_v2"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      Real-Time Collaboration
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="rtc-checkbox"
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>

                  <FormDescription>
                    Enable experimental real-time collaboration. This change
                    requires a page refresh to take effect.
                  </FormDescription>
                </div>
              )}
            />
            <FormField
              control={form.control}
              name="experimental.performant_table_charts"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      Performant Table Charts
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="performant-table-charts-checkbox"
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                  <IsOverridden
                    userConfig={config}
                    name="experimental.performant_table_charts"
                  />
                  <FormDescription>
                    Enable experimental table charts which are computed on the
                    backend.
                  </FormDescription>
                </div>
              )}
            />
            <FormField
              control={form.control}
              name="experimental.external_agents"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      External Agents
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="external-agents-checkbox"
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                  <IsOverridden
                    userConfig={config}
                    name="experimental.external_agents"
                  />
                  <FormDescription>
                    Enable experimental external agents such as Claude Code and
                    Gemini CLI. Learn more in the{" "}
                    <ExternalLink href="https://docs.marimo.io/guides/editor_features/agents/">
                      docs
                    </ExternalLink>
                    .
                  </FormDescription>
                </div>
              )}
            />
            <FormField
              control={form.control}
              name="experimental.chat_modes"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">Chat Mode</FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="chat-mode-checkbox"
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                  <IsOverridden
                    userConfig={config}
                    name="experimental.chat_modes"
                  />
                  <FormDescription>
                    Switch between different modes in the Chat sidebar, to
                    enable tool use.
                  </FormDescription>
                </div>
              )}
            />
          </SettingGroup>
        );
    }
  };

  const configMessage = (
    <p className="text-muted-secondary">
      User configuration is stored in <Kbd className="inline">marimo.toml</Kbd>
      <br />
      Run <Kbd className="inline">marimo config show</Kbd> in your terminal to
      show your current configuration and file location.
    </p>
  );

  return (
    <Form {...form}>
      <form
        ref={formElement}
        onChange={form.handleSubmit(onSubmit)}
        className="flex text-pretty overflow-hidden"
      >
        <Tabs
          value={activeCategory}
          onValueChange={(value) =>
            setActiveCategory(value as SettingCategoryId)
          }
          orientation="vertical"
          className="w-1/3 border-r h-full overflow-auto p-3"
        >
          <TabsList className="self-start max-h-none flex flex-col gap-2 shrink-0 bg-background flex-1 min-h-full">
            {categories.map((category) => (
              <TabsTrigger
                key={category.id}
                value={category.id}
                className="w-full text-left p-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground justify-start"
              >
                <div className="flex gap-4 items-center text-lg overflow-hidden">
                  <span
                    className={cn(
                      category.className,
                      "w-8 h-8 rounded flex items-center justify-center text-muted-foreground shrink-0",
                    )}
                  >
                    <category.Icon className="w-4 h-4" />
                  </span>
                  <span className="truncate">{category.label}</span>
                </div>
              </TabsTrigger>
            ))}

            <div className="p-2 text-xs text-muted-foreground self-start flex flex-col gap-1">
              <span>Version: {marimoVersion}</span>
              <span>Locale: {locale}</span>
            </div>

            <div className="flex-1" />
            {!isWasm() && configMessage}
          </TabsList>
        </Tabs>
        <div className="w-2/3 pl-6 gap-2 flex flex-col overflow-auto p-6">
          {renderBody()}
        </div>
      </form>
    </Form>
  );
};
