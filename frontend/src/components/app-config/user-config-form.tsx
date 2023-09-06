/* Copyright 2023 Marimo. All rights reserved. */
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { UserConfig, UserConfigSchema } from "../../core/config";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { toast } from "../ui/use-toast";
import { saveUserConfig } from "../../core/network/requests";
import { useUserConfig } from "../../core/state/config";
import { ThemeToggle } from "./theme-toggle";
import { NativeSelect } from "../ui/native-select";
import { KEYMAP_PRESETS } from "@/core/codemirror/keymaps/keymaps";

export const UserConfigForm: React.FC = () => {
  const [config, setConfig] = useUserConfig();

  // Create form
  const form = useForm<UserConfig>({
    resolver: zodResolver(UserConfigSchema),
    defaultValues: config,
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
      <form onChange={form.handleSubmit(onSubmit)} className="space-y-4">
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
        <FormField
          control={form.control}
          name="save.autosave_delay"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Autosave delay (seconds)</FormLabel>
              <FormControl>
                <Input
                  type="number"
                  disabled={form.getValues("save.autosave") !== "after_delay"}
                  {...field}
                  value={field.value / 1000}
                  min={1}
                  onChange={(e) =>
                    field.onChange(Number.parseInt(e.target.value) * 1000)
                  }
                />
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
                    checked={field.value}
                    onCheckedChange={(checked) => {
                      return field.onChange(Boolean(checked));
                    }}
                  />
                </FormControl>
                <FormLabel className="font-normal">
                  Trigger autocomplete while typing
                </FormLabel>
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
      </form>
      <ThemeToggle />
    </Form>
  );
};
