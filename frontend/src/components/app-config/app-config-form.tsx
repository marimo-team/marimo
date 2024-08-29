/* Copyright 2024 Marimo. All rights reserved. */
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
import {
  type AppConfig,
  AppConfigSchema,
  APP_WIDTHS,
  AppTitleSchema,
} from "../../core/config/config-schema";
import { Input } from "../ui/input";
import { NativeSelect } from "../ui/native-select";
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
            <FormItem
              className={"flex flex-row items-center space-x-1 space-y-0"}
            >
              <FormLabel>Width</FormLabel>
              <FormControl>
                <NativeSelect
                  data-testid="app-width-select"
                  onChange={(e) => field.onChange(e.target.value)}
                  value={field.value}
                  disabled={field.disabled}
                  className="inline-flex mr-2"
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
        <FormField
          control={form.control}
          name="app_title"
          render={({ field }) => (
            <div className="flex flex-col gap-y-1">
              <FormItem className="flex flex-row items-center space-x-1 space-y-0">
                <FormLabel>App title</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    value={field.value ?? ""}
                    onChange={(e) => {
                      field.onChange(e.target.value);
                      if (AppTitleSchema.safeParse(e.target.value).success) {
                        document.title = e.target.value;
                      }
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
              <FormDescription>
                The application title is put in the title tag in the HTML code
                and typically displayed in the title bar of the browser window.
              </FormDescription>
            </div>
          )}
        />
        <FormField
          control={form.control}
          name="css_file"
          render={({ field }) => (
            <div className="flex flex-col gap-y-1">
              <FormItem className="flex flex-row items-center space-x-1 space-y-0">
                <FormLabel className="flex-shrink-0">Custom CSS</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    value={field.value ?? ""}
                    placeholder="custom.css"
                    onChange={(e) => {
                      field.onChange(e.target.value);
                      if (AppTitleSchema.safeParse(e.target.value).success) {
                        document.title = e.target.value;
                      }
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
              <FormDescription>
                A filepath to a custom css file to be injected into the
                notebook.
              </FormDescription>
            </div>
          )}
        />
      </form>
    </Form>
  );
};
