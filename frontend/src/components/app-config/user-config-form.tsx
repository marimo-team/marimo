/* Copyright 2024 Marimo. All rights reserved. */
import { SettingSubtitle, SQL_OUTPUT_SELECT_OPTIONS } from "./common";

import React, { useRef } from "react";
import { type FieldPath, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { atom, useAtom, useAtomValue, useSetAtom } from "jotai";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { NumberField } from "@/components/ui/number-field";
import { Kbd } from "@/components/ui/kbd";
import { CopilotConfig } from "@/core/codemirror/copilot/copilot-config";
import { KEYMAP_PRESETS } from "@/core/codemirror/keymaps/keymaps";
import { configOverridesAtom, useUserConfig } from "@/core/config/config";
import {
  UserConfigSchema,
  PackageManagerNames,
  type UserConfig,
} from "@/core/config/config-schema";
import { getAppWidths } from "@/core/config/widths";
import { saveUserConfig } from "@/core/network/requests";
import { isWasm } from "@/core/wasm/utils";
import { THEMES } from "@/theme/useTheme";
import { keyboardShortcutsAtom } from "../editor/controls/keyboard-shortcuts";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  EditIcon,
  MonitorIcon,
  PackageIcon,
  CpuIcon,
  BrainIcon,
  FlaskConicalIcon,
  FolderCog2,
} from "lucide-react";
import { ExternalLink } from "../ui/links";
import { cn } from "@/utils/cn";
import { KNOWN_AI_MODELS, AWS_REGIONS } from "./constants";
import { Textarea } from "../ui/textarea";
import { get } from "lodash-es";
import { Tooltip } from "../ui/tooltip";
import { getMarimoVersion } from "@/core/dom/marimo-tag";
import { Badge } from "../ui/badge";
import { capabilitiesAtom } from "@/core/config/capabilities";
import { Banner } from "@/plugins/impl/common/error-banner";
import { OptionalFeatures } from "./optional-features";

const formItemClasses = "flex flex-row items-center space-x-1 space-y-0";
const categories = [
  {
    id: "editor",
    label: "Editor",
    Icon: EditIcon,
    className: "bg-[var(--blue-4)]",
  },
  {
    id: "display",
    label: "Display",
    Icon: MonitorIcon,
    className: "bg-[var(--grass-4)]",
  },
  {
    id: "packageManagement",
    label: "Package Management",
    Icon: PackageIcon,
    className: "bg-[var(--red-4)]",
  },
  {
    id: "runtime",
    label: "Runtime",
    Icon: CpuIcon,
    className: "bg-[var(--amber-4)]",
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
    className: "bg-[var(--orange-4)]",
  },
  {
    id: "labs",
    label: "Labs",
    Icon: FlaskConicalIcon,
    className: "bg-[var(--slate-4)]",
  },
] as const;

export type SettingCategoryId = (typeof categories)[number]["id"];

export const activeUserConfigCategoryAtom = atom<SettingCategoryId>(
  categories[0].id,
);

export const UserConfigForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();
  const formElement = useRef<HTMLFormElement>(null);
  const setKeyboardShortcutsOpen = useSetAtom(keyboardShortcutsAtom);
  const [activeCategory, setActiveCategory] = useAtom(
    activeUserConfigCategoryAtom,
  );
  const capabilities = useAtomValue(capabilitiesAtom);

  // Create form
  const form = useForm<UserConfig>({
    resolver: zodResolver(UserConfigSchema),
    defaultValues: config,
  });

  const onSubmit = async (values: UserConfig) => {
    await saveUserConfig({ config: values }).then(() => {
      setConfig(values);
    });
  };

  const isWasmRuntime = isWasm();

  const renderCopilotProvider = () => {
    const copilot = form.getValues("completion.copilot");
    if (copilot === false) {
      return null;
    }

    if (copilot === "codeium") {
      return (
        <>
          <p className="text-sm text-muted-secondary">
            To get a Codeium API key, follow{" "}
            <ExternalLink href="https://docs.marimo.io/guides/editor_features/ai_completion.html#codeium-copilot">
              these instructions
            </ExternalLink>
            .
          </p>
          <FormField
            control={form.control}
            name="completion.codeium_api_key"
            render={({ field }) => (
              <FormItem className={formItemClasses}>
                <FormLabel>API Key</FormLabel>
                <FormControl>
                  <Input
                    data-testid="codeium-api-key-input"
                    className="m-0 inline-flex"
                    placeholder="key"
                    {...field}
                    value={field.value || ""}
                  />
                </FormControl>
                <FormMessage />
                <IsOverridden
                  userConfig={config}
                  name="completion.codeium_api_key"
                />
              </FormItem>
            )}
          />
        </>
      );
    }

    if (copilot === "github") {
      return <CopilotConfig />;
    }

    if (copilot === "custom") {
      return (
        <>
          <p className="text-sm text-muted-secondary">
            Configure your custom AI completion provider with the following
            settings.
          </p>
          <FormField
            control={form.control}
            name="completion.model"
            render={({ field }) => (
              <FormItem className={formItemClasses}>
                <FormLabel>Model</FormLabel>
                <FormControl>
                  <Input
                    data-testid="custom-model-input"
                    className="m-0 inline-flex"
                    placeholder="Qwen2.5-Coder-7B"
                    {...field}
                    value={field.value || ""}
                  />
                </FormControl>
                <FormMessage />
                <IsOverridden userConfig={config} name="completion.model" />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="completion.base_url"
            render={({ field }) => (
              <FormItem className={formItemClasses}>
                <FormLabel>Base URL</FormLabel>
                <FormControl>
                  <Input
                    data-testid="custom-base-url-input"
                    className="m-0 inline-flex"
                    placeholder="http://localhost:11434/v1"
                    {...field}
                    value={field.value || ""}
                  />
                </FormControl>
                <FormMessage />
                <IsOverridden userConfig={config} name="completion.base_url" />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="completion.api_key"
            render={({ field }) => (
              <FormItem className={formItemClasses}>
                <FormLabel>API Key</FormLabel>
                <FormControl>
                  <Input
                    data-testid="custom-api-key-input"
                    className="m-0 inline-flex"
                    placeholder="key"
                    {...field}
                    value={field.value || ""}
                  />
                </FormControl>
                <FormMessage />
                <IsOverridden userConfig={config} name="completion.api_key" />
              </FormItem>
            )}
          />
        </>
      );
    }
  };

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
            </SettingGroup>
            <SettingGroup title="Language Servers">
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
                          pylsp
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
              <FormDescription>
                See the{" "}
                <ExternalLink href="https://docs.marimo.io/guides/editor_features/language_server/">
                  docs
                </ExternalLink>{" "}
                for more information about language server support.
              </FormDescription>

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
              <FormField
                control={form.control}
                name="display.dataframes"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Dataframe viewer</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="display-dataframes-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={field.value}
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {["rich", "plain"].map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="display.dataframes"
                      />
                    </FormItem>

                    <FormDescription>
                      Whether to use marimo's rich dataframe viewer or a plain
                      HTML table. This requires restarting your notebook to take
                      effect.
                    </FormDescription>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                name="display.default_table_page_size"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Default table page size</FormLabel>
                      <FormControl>
                        <NumberField
                          data-testid="default-table-page-size-input"
                          className="m-0 w-24"
                          {...field}
                          value={field.value}
                          minValue={1}
                          step={1}
                          onChange={(value) => {
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
                        name="display.default_table_page_size"
                      />
                    </FormItem>
                    <FormDescription>
                      The default number of rows displayed in dataframes and SQL
                      results.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
          </>
        );
      case "packageManagement":
        return (
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
                    When marimo comes across a module that is not installed, you
                    will be prompted to install it using your preferred package
                    manager. Learn more in the{" "}
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
        );
      case "runtime":
        return (
          <SettingGroup title="Runtime configuration">
            <FormField
              control={form.control}
              name="runtime.default_sql_output"
              render={({ field }) => (
                <div className="flex flex-col space-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel>Default SQL output</FormLabel>
                    <FormControl>
                      <NativeSelect
                        data-testid="user-config-sql-output-select"
                        onChange={(e) => field.onChange(e.target.value)}
                        value={field.value}
                        disabled={field.disabled}
                        className="inline-flex mr-2"
                      >
                        {SQL_OUTPUT_SELECT_OPTIONS.map((option) => (
                          <option value={option.value} key={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </NativeSelect>
                    </FormControl>
                    <FormMessage />
                    <IsOverridden
                      userConfig={config}
                      name="runtime.default_sql_output"
                    />
                  </FormItem>

                  <FormDescription>
                    The default SQL output format for new notebooks; overridden
                    by "sql_output" in the application config.
                  </FormDescription>
                </div>
              )}
            />
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
        return (
          <>
            <SettingGroup title="AI Code Completion">
              <p className="text-sm text-muted-secondary">
                You may use GitHub Copilot, Codeium, or a custom provider (e.g.
                Ollama) for AI code completion.
              </p>

              <FormField
                control={form.control}
                name="completion.copilot"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Provider</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="copilot-select"
                          onChange={(e) => {
                            if (e.target.value === "none") {
                              field.onChange(false);
                            } else {
                              field.onChange(e.target.value);
                            }
                          }}
                          value={
                            field.value === true
                              ? "github"
                              : field.value === false
                                ? "none"
                                : field.value
                          }
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {["none", "github", "codeium", "custom"].map(
                            (option) => (
                              <option value={option} key={option}>
                                {option}
                              </option>
                            ),
                          )}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="completion.copilot"
                      />
                    </FormItem>
                  </div>
                )}
              />

              {renderCopilotProvider()}
            </SettingGroup>
            <SettingGroup title="AI Keys">
              <FormField
                control={form.control}
                name="ai.open_ai.api_key"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>OpenAI API Key</FormLabel>
                      <FormControl>
                        <Input
                          data-testid="ai-openai-api-key-input"
                          className="m-0 inline-flex"
                          placeholder="sk-proj..."
                          {...field}
                          onChange={(e) => {
                            const value = e.target.value;
                            // Don't allow *
                            if (!value.includes("*")) {
                              field.onChange(value);
                            }
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.open_ai.api_key"
                      />
                    </FormItem>
                    <FormDescription>
                      Your OpenAI API key from{" "}
                      <ExternalLink href="https://platform.openai.com/account/api-keys">
                        platform.openai.com
                      </ExternalLink>
                      .
                    </FormDescription>
                  </div>
                )}
              />

              <FormField
                control={form.control}
                name="ai.anthropic.api_key"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Anthropic API Key</FormLabel>
                      <FormControl>
                        <Input
                          data-testid="ai-anthropic-api-key-input"
                          className="m-0 inline-flex"
                          placeholder="sk-ant..."
                          {...field}
                          onChange={(e) => {
                            const value = e.target.value;
                            // Don't allow *
                            if (!value.includes("*")) {
                              field.onChange(value);
                            }
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.anthropic.api_key"
                      />
                    </FormItem>
                    <FormDescription>
                      Your Anthropic API key from{" "}
                      <ExternalLink href="https://console.anthropic.com/settings/keys">
                        console.anthropic.com
                      </ExternalLink>
                      .
                    </FormDescription>
                  </div>
                )}
              />

              <FormField
                control={form.control}
                name="ai.google.api_key"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Google AI API Key</FormLabel>
                      <FormControl>
                        <Input
                          data-testid="ai-google-api-key-input"
                          className="m-0 inline-flex"
                          placeholder="AI..."
                          {...field}
                          onChange={(e) => {
                            const value = e.target.value;
                            // Don't allow *
                            if (!value.includes("*")) {
                              field.onChange(value);
                            }
                          }}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.google.api_key"
                      />
                    </FormItem>
                    <FormDescription>
                      Your Google AI API key from{" "}
                      <ExternalLink href="https://aistudio.google.com/app/apikey">
                        aistudio.google.com
                      </ExternalLink>
                      .
                    </FormDescription>
                  </div>
                )}
              />

              <p className="text-sm font-semibold mt-3">
                AWS Bedrock Configuration
              </p>
              <p className="text-sm text-muted-secondary mb-2">
                To use AWS Bedrock, you need to configure AWS credentials and
                region. See the{" "}
                <ExternalLink href="https://docs.marimo.io/guides/editor_features/ai_completion.html#aws-bedrock">
                  documentation
                </ExternalLink>{" "}
                for more details.
              </p>
              <FormField
                control={form.control}
                disabled={isWasmRuntime}
                name="ai.bedrock.region_name"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>AWS Region</FormLabel>
                      <FormControl>
                        <NativeSelect
                          data-testid="bedrock-region-select"
                          onChange={(e) => field.onChange(e.target.value)}
                          value={
                            typeof field.value === "string"
                              ? field.value
                              : "us-east-1"
                          }
                          disabled={field.disabled}
                          className="inline-flex mr-2"
                        >
                          {AWS_REGIONS.map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.bedrock.region_name"
                      />
                    </FormItem>
                    <FormDescription>
                      The AWS region where Bedrock service is available.
                    </FormDescription>
                  </div>
                )}
              />

              <FormField
                control={form.control}
                disabled={isWasmRuntime}
                name="ai.bedrock.profile_name"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>AWS Profile Name (Optional)</FormLabel>
                      <FormControl>
                        <Input
                          data-testid="bedrock-profile-input"
                          className="m-0 inline-flex"
                          placeholder="default"
                          {...field}
                          value={field.value || ""}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.bedrock.profile_name"
                      />
                    </FormItem>
                    <FormDescription>
                      The AWS profile name from your ~/.aws/credentials file.
                      Leave blank to use your default AWS credentials.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>

            <SettingGroup title="AI Assist">
              <p className="text-sm text-muted-secondary">
                Add an API key to <Kbd className="inline">marimo.toml</Kbd> to
                activate marimo's AI assistant; see{" "}
                <ExternalLink href="https://docs.marimo.io/guides/editor_features/ai_completion.html">
                  docs
                </ExternalLink>{" "}
                for more info.
              </p>
              <FormField
                control={form.control}
                disabled={isWasmRuntime}
                name="ai.open_ai.base_url"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Base URL</FormLabel>
                      <FormControl>
                        <Input
                          data-testid="ai-base-url-input"
                          className="m-0 inline-flex"
                          placeholder="https://api.openai.com/v1"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.open_ai.base_url"
                      />
                    </FormItem>
                    <FormDescription>
                      This URL can be any OpenAI-compatible API endpoint.
                    </FormDescription>
                  </div>
                )}
              />
              <FormField
                control={form.control}
                disabled={isWasmRuntime}
                name="ai.open_ai.model"
                render={({ field }) => (
                  <div className="flex flex-col space-y-1">
                    <FormItem className={formItemClasses}>
                      <FormLabel>Model</FormLabel>
                      <FormControl>
                        <Input
                          list="ai-model-datalist"
                          data-testid="ai-model-input"
                          className="m-0 inline-flex"
                          placeholder="gpt-4-turbo"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden
                        userConfig={config}
                        name="ai.open_ai.model"
                      />
                    </FormItem>
                    <datalist id="ai-model-datalist">
                      {KNOWN_AI_MODELS.map((model) => (
                        <option value={model} key={model}>
                          {model}
                        </option>
                      ))}
                    </datalist>
                    <FormDescription>
                      If the model starts with "claude-", we will use your
                      Anthropic API key. If the model starts with "gemini-", we
                      will use your Google AI API key. If the model starts with
                      a "bedrock/" prefix followed by a model id (e.g.,
                      "bedrock/anthropic.claude-3-sonnet-20240229"), we will use
                      your AWS Bedrock configuration. Otherwise, we will use
                      your OpenAI API key.
                    </FormDescription>
                  </div>
                )}
              />

              <FormField
                control={form.control}
                name="ai.rules"
                render={({ field }) => (
                  <div className="flex flex-col">
                    <FormItem>
                      <FormLabel>Custom Rules</FormLabel>
                      <FormControl>
                        <Textarea
                          data-testid="ai-rules-input"
                          className="m-0 inline-flex w-full h-32 p-2 text-sm"
                          placeholder="e.g. Always use type hints; prefer polars over pandas"
                          {...field}
                          value={field.value}
                        />
                      </FormControl>
                      <FormMessage />
                      <IsOverridden userConfig={config} name="ai.rules" />
                    </FormItem>
                    <FormDescription>
                      Custom rules to include in all AI completion prompts.
                    </FormDescription>
                  </div>
                )}
              />
            </SettingGroup>
          </>
        );
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
              name="experimental.inline_ai_tooltip"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">
                      AI Edit Tooltip
                    </FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="inline-ai-checkbox"
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                  <FormDescription>
                    Enable experimental "Edit with AI" tooltip when selecting
                    code.
                  </FormDescription>
                </div>
              )}
            />
            <FormField
              control={form.control}
              name="experimental.table_charts"
              render={({ field }) => (
                <div className="flex flex-col gap-y-1">
                  <FormItem className={formItemClasses}>
                    <FormLabel className="font-normal">Table Charts</FormLabel>
                    <FormControl>
                      <Checkbox
                        data-testid="data-table-plugin-checkbox"
                        checked={field.value === true}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                  <FormDescription>
                    Enable experimental charting feature on tables. Data is
                    saved in local storage. May not be performant.
                  </FormDescription>
                </div>
              )}
            />
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
                      "w-8 h-8 rounded flex items-center justify-center text-muted-foreground flex-shrink-0",
                    )}
                  >
                    <category.Icon className="w-4 h-4" />
                  </span>
                  <span className="truncate">{category.label}</span>
                </div>
              </TabsTrigger>
            ))}

            <div className="p-2 text-xs text-muted-foreground self-start">
              <span>Version: {getMarimoVersion()}</span>
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

const SettingGroup = ({
  title,
  children,
}: { title: string; children: React.ReactNode }) => {
  return (
    <div className="flex flex-col gap-4 pb-4">
      <SettingSubtitle>{title}</SettingSubtitle>
      {children}
    </div>
  );
};

const IsOverridden = ({
  userConfig,
  name,
}: {
  userConfig: UserConfig;
  name: FieldPath<UserConfig>;
}) => {
  const currentValue = get(userConfig, name);
  const overrides = useAtomValue(configOverridesAtom);
  const overriddenValue = get(overrides as UserConfig, name);
  if (overriddenValue == null) {
    return null;
  }

  if (currentValue === overriddenValue) {
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
      <span className="text-[var(--amber-12)] text-xs flex items-center gap-1 border rounded px-2 py-1 bg-[var(--amber-2)] border-[var(--amber-6)] ml-1">
        <FolderCog2 className="w-3 h-3" />
        Overridden by pyproject.toml [{String(overriddenValue)}]
      </span>
    </Tooltip>
  );
};
