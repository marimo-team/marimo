/* Copyright 2023 Marimo. All rights reserved. */
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
import { UserConfig, UserConfigSchema } from "../../core/config/config";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { toast } from "../ui/use-toast";
import { saveUserConfig } from "../../core/network/requests";
import { useUserConfig } from "../../core/state/config";
import { ThemeToggle } from "./theme-toggle";
import { NativeSelect } from "../ui/native-select";
import { KEYMAP_PRESETS } from "@/core/codemirror/keymaps/keymaps";
import { CopilotConfig } from "@/core/codemirror/copilot/copilot-config";
import { Switch } from "../ui/switch";
import { SettingTitle, SettingDescription, SettingSubtitle } from "./common";

export const UserConfigForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();

  // Create form
  const form = useForm<UserConfig>({
    resolver: zodResolver(UserConfigSchema),
    defaultValues: config as DefaultValues<UserConfig>,
  });

  const onSubmit = async (values: UserConfig) => {
    await saveUserConfig({ config: values })
      .then(() => {
        setConfig(values);
      })
      .catch(() => {
        toast({ title: "Failed to save" });
      });
  };

  return (
    <Form {...form}>
      <form
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
                      checked={field.value === "after_delay"}
                      onCheckedChange={(checked) => {
                        return field.onChange(
                          checked === true ? "after_delay" : "off"
                        );
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
                  <span className="inline-flex mx-2">
                    <Input
                      type="number"
                      className="m-0 w-20 inline-flex"
                      disabled={
                        form.getValues("save.autosave") !== "after_delay"
                      }
                      {...field}
                      value={field.value / 1000}
                      min={1}
                      onChange={(e) =>
                        field.onChange(Number.parseInt(e.target.value) * 1000)
                      }
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
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        return field.onChange(checked);
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
            name="completion.activate_on_typing"
            render={({ field }) => (
              <div className="flex flex-col space-y-1">
                <FormItem className="flex flex-row items-start space-x-2 space-y-0">
                  <FormControl>
                    <Checkbox
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        return field.onChange(Boolean(checked));
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
                    onChange={(e) => field.onChange(e.target.value)}
                    value={field.value}
                    className="inline-flex mx-2"
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
        <ThemeToggle />
        <div className="flex flex-col gap-3">
          <SettingSubtitle>Runtime</SettingSubtitle>
          <FormField
            control={form.control}
            name="runtime.auto_instantiate"
            render={({ field }) => (
              <FormItem className="flex flex-row items-start space-x-2 space-y-0">
                <FormControl>
                  <Checkbox
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
        </div>
        <div className="flex flex-col gap-3">
          <SettingSubtitle>GitHub Copilot</SettingSubtitle>
          <FormField
            control={form.control}
            name="completion.copilot"
            render={({ field }) => (
              <div className="flex flex-col gap-2">
                <FormItem className="flex flex-row items-center space-x-2 space-y-0">
                  <FormControl>
                    <Switch
                      size={"sm"}
                      checked={field.value}
                      onCheckedChange={(checked) => {
                        return field.onChange(Boolean(checked));
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
