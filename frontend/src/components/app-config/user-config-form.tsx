/* Copyright 2024 Marimo. All rights reserved. */
import { SettingSubtitle } from "./common";

import React, { useRef } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { atom, useAtom, useSetAtom } from "jotai";
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
import { useUserConfig } from "@/core/config/config";
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
} from "lucide-react";
import { cn } from "@/utils/cn";
import { KNOWN_AI_MODELS } from "./constants";

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
] as const;

type CategoryId = (typeof categories)[number]["id"];

export const activeUserConfigCategoryAtom = atom<CategoryId>(categories[0].id);

export const UserConfigForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();
  const formElement = useRef<HTMLFormElement>(null);
  const setKeyboardShortcutsOpen = useSetAtom(keyboardShortcutsAtom);
  const [activeCategory, setActiveCategory] = useAtom(
    activeUserConfigCategoryAtom,
  );

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
            <a
              className="text-link hover:underline"
              href="https://docs.marimo.io/guides/editor_features/ai_completion.html#codeium-copilot"
              target="_blank"
              rel="noreferrer"
            >
              these instructions
            </a>
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
              </FormItem>
            )}
          />
        </>
      );
    }
    if (copilot === "github") {
      return <CopilotConfig />;
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
                    </FormItem>

                    <FormDescription>
                      Whether to use marimo's rich dataframe viewer or a plain
                      HTML table. This requires restarting your notebook to take
                      effect.
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
                  </FormItem>

                  <FormDescription>
                    When marimo comes across a module that is not installed, you
                    will be prompted to install it using your preferred package
                    manager. Learn more in the{" "}
                    <a
                      className="text-link hover:underline"
                      href="https://docs.marimo.io/guides/editor_features/package_management.html"
                      target="_blank"
                      rel="noreferrer"
                    >
                      docs
                    </a>
                    .
                    <br />
                    <br />
                    Running marimo in a{" "}
                    <a
                      className="text-link hover:underline"
                      href="https://docs.marimo.io/guides/editor_features/package_management.html#running-marimo-in-a-sandbox-environment-uv-only"
                      target="_blank"
                      rel="noreferrer"
                    >
                      sandboxed environment
                    </a>{" "}
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

            <FormDescription>
              Learn more in the{" "}
              <a
                className="text-link hover:underline"
                href="https://docs.marimo.io/guides/reactivity.html#runtime-configuration"
                target="_blank"
                rel="noreferrer"
              >
                docs
              </a>
              .
            </FormDescription>
          </SettingGroup>
        );
      case "ai":
        return (
          <>
            <SettingGroup title="AI Assist">
              <p className="text-sm text-muted-secondary">
                Add an API key to <Kbd className="inline">marimo.toml</Kbd> to
                activate marimo's AI assistant; see{" "}
                <a
                  className="text-link hover:underline"
                  href="https://docs.marimo.io/guides/editor_features/ai_completion.html"
                  target="_blank"
                  rel="noreferrer"
                >
                  docs
                </a>{" "}
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
                      will use your Google AI API key. Otherwise, we will use
                      your OpenAI API key.
                    </FormDescription>
                  </div>
                )}
              />
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
                      </FormItem>
                      <FormDescription>
                        Your OpenAI API key from{" "}
                        <a
                          className="text-link hover:underline"
                          href="https://platform.openai.com/account/api-keys"
                          target="_blank"
                          rel="noreferrer"
                        >
                          platform.openai.com
                        </a>
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
                      </FormItem>
                      <FormDescription>
                        Your Anthropic API key from{" "}
                        <a
                          className="text-link hover:underline"
                          href="https://console.anthropic.com/settings/keys"
                          target="_blank"
                          rel="noreferrer"
                        >
                          console.anthropic.com
                        </a>
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
                      </FormItem>
                      <FormDescription>
                        Your Google AI API key from{" "}
                        <a
                          className="text-link hover:underline"
                          href="https://aistudio.google.com/app/apikey"
                          target="_blank"
                          rel="noreferrer"
                        >
                          aistudio.google.com
                        </a>
                        .
                      </FormDescription>
                    </div>
                  )}
                />
              </SettingGroup>
            </SettingGroup>
            <SettingGroup title="AI Code Completion">
              <p className="text-sm text-muted-secondary">
                You may use GitHub Copilot or Codeium for AI code completion.
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
                          {["none", "github", "codeium"].map((option) => (
                            <option value={option} key={option}>
                              {option}
                            </option>
                          ))}
                        </NativeSelect>
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  </div>
                )}
              />

              {renderCopilotProvider()}
            </SettingGroup>
          </>
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
          onValueChange={(value) => setActiveCategory(value as CategoryId)}
          orientation="vertical"
          className="w-1/3 pr-4 border-r h-full overflow-auto p-6"
        >
          <TabsList className="self-start max-h-none flex flex-col gap-2 flex-shrink-0 bg-background flex-1 min-h-full">
            {categories.map((category) => (
              <TabsTrigger
                key={category.id}
                value={category.id}
                className="w-full text-left p-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground justify-start"
              >
                <div className="flex gap-4 items-center text-lg">
                  <span
                    className={cn(
                      category.className,
                      "w-8 h-8 rounded flex items-center justify-center text-muted-foreground",
                    )}
                  >
                    <category.Icon className="w-4 h-4" />
                  </span>
                  {category.label}
                </div>
              </TabsTrigger>
            ))}
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
      <SettingSubtitle className="text-base">{title}</SettingSubtitle>
      {children}
    </div>
  );
};
