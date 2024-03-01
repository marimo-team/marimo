/* Copyright 2024 Marimo. All rights reserved. */
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  AppConfig,
  AppConfigSchema,
  APP_WIDTHS,
} from "../../core/config/config-schema";
import { NativeSelect } from "../ui/native-select";
import { toast } from "../ui/use-toast";
import { useAppConfig } from "@/core/config/config";
import { saveAppConfig } from "@/core/network/requests";
import { SettingTitle, SettingDescription } from "./common";
import { useEffect } from "react";

export const AppConfigForm: React.FC = () => {
  const [config, setConfig] = useAppConfig();

  // Create form
  const form = useForm<AppConfig>({
    resolver: zodResolver(AppConfigSchema),
    defaultValues: config,
  });

  const onSubmit = async (values: AppConfig) => {
    await saveAppConfig({ config: values })
      .then(() => {
        setConfig(values);
      })
      .catch(() => {
        setConfig(values);
        toast({ title: "Failed to save" });
      });
  };

  // When width is changed, dispatch a resize event so widgets know to resize
  useEffect(() => {
    window.dispatchEvent(new Event("resize"));
  }, [config.width]);

  return (
    <Form {...form}>
      <form
        onChange={form.handleSubmit(onSubmit)}
        className="flex flex-col gap-4"
      >
        <div>
          <SettingTitle>Application Config</SettingTitle>
          <SettingDescription>
            Settings applied to this notebook
          </SettingDescription>
        </div>
        <FormField
          control={form.control}
          name="width"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Width</FormLabel>
              <FormControl>
                <NativeSelect
                  onChange={(e) => field.onChange(e.target.value)}
                  value={field.value}
                  disabled={field.disabled}
                  className="inline-flex mx-2"
                >
                  {APP_WIDTHS.map((option) => (
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
    </Form>
  );
};
