/* Copyright 2024 Marimo. All rights reserved. */
import { zodResolver } from "@hookform/resolvers/zod";
import { DefaultValues, useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { UserConfig, UserConfigSchema } from "../../core/config/config-schema";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { saveUserConfig } from "../../core/network/requests";
import { useUserConfig } from "../../core/config/config";
import { NativeSelect } from "../ui/native-select";
import { KEYMAP_PRESETS } from "@/core/codemirror/keymaps/keymaps";
import { CopilotConfig } from "@/core/codemirror/copilot/copilot-config";
import { Switch } from "../ui/switch";
import { SettingTitle, SettingDescription, SettingSubtitle } from "./common";
import { THEMES } from "@/theme/useTheme";
import { isPyodide } from "@/core/pyodide/utils";
import { PackageManagerNames } from "../../core/config/config-schema";
import { Kbd } from "../ui/kbd";
import { NumberField } from "@/components/ui/number-field";
import { useRef } from "react";

export const UserConfigForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();
  const formElement = useRef<HTMLFormElement>(null);

  // Create form
  const form = useForm<UserConfig>({
    resolver: zodResolver(UserConfigSchema),
    defaultValues: config as DefaultValues<UserConfig>,
  });

  const onSubmit = async (values: UserConfig) => {
    await saveUserConfig({ config: values }).then(() => {
      setConfig(values);
    });
  };

  const isWasm = isPyodide();

  return (
    <Form {...form}>
      <form
        ref={formElement}
        onChange={form.handleSubmit(onSubmit)}
        className="flex flex-col gap-5"
      >
        <div>
          <SettingTitle>User Config</SettingTitle>
          <SettingDescription>
            Settings applied to all marimo notebooks
          </SettingDescription>
        </div>
        <div className="flex flex-col gap-3">
          <SettingSubtitle>Editor</SettingSubtitle>
          <div>
            <FormField
              control={form.control}
              name="save.autosave"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-2 space-y-0">
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
                  <FormLabel className="font-normal">Autosave</FormLabel>
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="save.autosave_delay"
            render={({ field }) => (
              <FormItem className="mb-2">
                <FormLabel>Autosave delay (seconds)</FormLabel>
                <FormControl>
                  <span className="inline-flex mr-2">
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
                        onSubmit(form.getValues());
                      }}
                    />
                  </span>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <div>
            <FormField
              control={form.control}
              name="save.format_on_save"
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-2 space-y-0">
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
                  <FormLabel className="font-normal">Format on save</FormLabel>
                </FormItem>
              )}
            />
          </div>
          <FormField
            control={form.control}
            name="formatting.line_length"
            render={({ field }) => (
              <FormItem className="mb-2">
                <FormLabel>Line length</FormLabel>
                <FormDescription>
                  Maximum line length when formatting code.
                </FormDescription>
                <FormControl>
                  <span className="inline-flex mr-2">
                    <NumberField
                      data-testid="line-length-input"
                      className="m-0 w-24"
                      {...field}
                      value={field.value}
                      minValue={1}
                      maxValue={1000}
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
          <FormField
            control={form.control}
            name="completion.activate_on_typing"
            render={({ field }) => (
              <div className="flex flex-col space-y-1">
                <FormItem className="flex flex-row items-start space-x-2 space-y-0">
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
                  <FormLabel className="font-normal">Autocomplete</FormLabel>
                </FormItem>
                <FormDescription>
                  When unchecked, code completion is still available through a
                  hotkey.
                </FormDescription>
              </div>
            )}
          />
          <FormField
            control={form.control}
            name="keymap.preset"
            render={({ field }) => (
              <FormItem>
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
            )}
          />
        </div>
        <div className="flex flex-col gap-3">
          <SettingSubtitle>Display</SettingSubtitle>
          <FormField
            control={form.control}
            name="display.theme"
            render={({ field }) => (
              <FormItem>
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
            )}
          />
          <FormField
            control={form.control}
            name="display.code_editor_font_size"
            render={({ field }) => (
              <FormItem className="mb-2">
                <FormLabel>Code editor font size</FormLabel>
                <FormControl>
                  <span className="inline-flex mr-2">
                    <NumberField
                      data-testid="code-editor-font-size-input"
                      className="m-0 w-24"
                      {...field}
                      value={field.value}
                      minValue={8}
                      maxValue={20}
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
          <FormField
            control={form.control}
            name="display.cell_output"
            render={({ field }) => (
              <FormItem className="mb-2">
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
                <FormDescription>
                  Where to display cell's output.
                </FormDescription>
              </FormItem>
            )}
          />
        </div>

        <div className="flex flex-col gap-3">
          <SettingSubtitle>Package Management</SettingSubtitle>
          <FormField
            control={form.control}
            disabled={isWasm}
            name="package_management.manager"
            render={({ field }) => (
              <FormItem>
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
            )}
          />
        </div>
        <div className="flex flex-col gap-3">
          <SettingSubtitle>Runtime</SettingSubtitle>
          <FormField
            control={form.control}
            name="runtime.auto_instantiate"
            render={({ field }) => (
              <FormItem className="flex flex-row items-start space-x-2 space-y-0">
                <FormControl>
                  <Checkbox
                    data-testid="auto-instantiate-checkbox"
                    disabled={field.disabled}
                    checked={field.value}
                    onCheckedChange={field.onChange}
                  />
                </FormControl>
                <FormLabel className="font-normal">
                  Autorun on startup
                </FormLabel>
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="runtime.auto_reload"
            render={({ field }) => (
              <div className="flex flex-col gap-y-1">
                <FormItem className="flex flex-row items-start space-x-2 space-y-0">
                  <FormControl>
                    <Checkbox
                      data-testid="auto-reload-checkbox"
                      disabled={field.disabled}
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                  <FormLabel className="font-normal">
                    Autoreload modules
                  </FormLabel>
                </FormItem>
                <FormDescription>
                  When checked, marimo will automatically reload modules before
                  executing cells.
                </FormDescription>
              </div>
            )}
          />
        </div>
        <div className="flex flex-col gap-3">
          <SettingSubtitle>AI Assist</SettingSubtitle>
          <p className="text-sm text-muted-secondary">
            You will need to store an API key in your{" "}
            <Kbd className="inline">~/.marimo.toml</Kbd> file. See the{" "}
            <a
              className="text-link hover:underline"
              href="https://docs.marimo.io/guides/ai_completion.html"
              target="_blank"
              rel="noreferrer"
            >
              documentation
            </a>{" "}
            for more information.
          </p>
          <FormField
            control={form.control}
            disabled={isWasm}
            name="ai.open_ai.base_url"
            render={({ field }) => (
              <FormItem className="mb-2">
                <FormLabel>Base URL</FormLabel>
                <FormControl>
                  <Input
                    data-testid="code-editor-font-size-input"
                    className="m-0 inline-flex"
                    {...field}
                    value={field.value}
                    placeholder="https://api.openai.com"
                    onChange={(e) => field.onChange(e.target.value)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            disabled={isWasm}
            name="ai.open_ai.model"
            render={({ field: { value, onChange, ...field } }) => (
              <FormItem className="mb-2">
                <FormLabel>Model</FormLabel>
                <FormControl>
                  <Input
                    data-testid="code-editor-font-size-input"
                    className="m-0 inline-flex"
                    {...field}
                    defaultValue={value}
                    placeholder="gpt-3.5-turbo"
                    onBlur={(e) => onChange(e.target.value)}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
        <div className="flex flex-col gap-3">
          <SettingSubtitle>GitHub Copilot</SettingSubtitle>
          <FormField
            control={form.control}
            disabled={isWasm}
            name="completion.copilot"
            render={({ field }) => (
              <div className="flex flex-col gap-2">
                <FormItem className="flex flex-row items-center space-x-2 space-y-0">
                  <FormControl>
                    <Switch
                      data-testid="copilot-switch"
                      size={"sm"}
                      checked={field.value}
                      disabled={field.disabled}
                      onCheckedChange={(checked) => {
                        field.onChange(Boolean(checked));
                      }}
                    />
                  </FormControl>
                  <FormLabel className="font-normal flex">Enable</FormLabel>
                </FormItem>
                {field.value && <CopilotConfig />}
              </div>
            )}
          />
        </div>
      </form>
    </Form>
  );
};
