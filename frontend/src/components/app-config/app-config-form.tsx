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
  AppTitleSchema,
} from "../../core/config/config-schema";
import { getAppWidths } from "@/core/config/widths";
import { Input } from "../ui/input";
import { NativeSelect } from "../ui/native-select";
import { useAppConfig } from "@/core/config/config";
import { saveAppConfig } from "@/core/network/requests";
import { SettingTitle, SettingDescription } from "./common";
import { useEffect } from "react";
import { Checkbox } from "../ui/checkbox";
import { arrayToggle } from "@/utils/arrays";
import { Kbd } from "../ui/kbd";
import { ExternalLink } from "../ui/links";
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
                  {getAppWidths().map((option) => (
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
        <FormField
          control={form.control}
          name="html_head_file"
          render={({ field }) => (
            <div className="flex flex-col gap-y-1">
              <FormItem className="flex flex-row items-center space-x-1 space-y-0">
                <FormLabel className="flex-shrink-0">HTML Head</FormLabel>
                <FormControl>
                  <Input
                    {...field}
                    value={field.value ?? ""}
                    placeholder="head.html"
                    onChange={(e) => {
                      field.onChange(e.target.value);
                    }}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
              <FormDescription>
                A filepath to an HTML file to be injected into the{" "}
                <Kbd className="inline">{"<head/>"}</Kbd> section of the
                notebook. Use this to add analytics, custom fonts, meta tags, or
                external scripts.
              </FormDescription>
            </div>
          )}
        />
        <FormField
          control={form.control}
          name="sql_output"
          render={({ field }) => (
            <div className="flex flex-col gap-y-1">
              <FormItem
                className={"flex flex-row items-center space-x-1 space-y-0"}
              >
                <FormLabel>SQL Output Type</FormLabel>
                <FormControl>
                  <NativeSelect
                    data-testid="sql-output-select"
                    onChange={(e) => field.onChange(e.target.value)}
                    value={field.value}
                    disabled={field.disabled}
                    className="inline-flex mr-2"
                  >
                    <option value="auto">Auto (Default)</option>
                    <option value="native">Native</option>
                    <option value="polars">Polars</option>
                    <option value="lazy-polars">Lazy Polars</option>
                    <option value="pandas">Pandas</option>
                  </NativeSelect>
                </FormControl>
                <FormMessage />
              </FormItem>
              <FormDescription>
                The Python type returned by a SQL cell. For best performance
                with large datasets, we recommend using{" "}
                <Kbd className="inline">native</Kbd>. See the{" "}
                <ExternalLink href="http://docs.marimo.io/guides/working_with_data/sql">
                  SQL guide
                </ExternalLink>{" "}
                for more information.
              </FormDescription>
            </div>
          )}
        />
        <FormField
          control={form.control}
          name="auto_download"
          render={({ field }) => (
            <div className="flex flex-col gap-y-1">
              <div className="text-base font-bold text-muted-foreground">
                Auto-download
              </div>
              <FormItem className="flex flex-col gap-2">
                <FormControl>
                  <div className="flex gap-4">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="html-checkbox"
                        checked={field.value.includes("html")}
                        onCheckedChange={() => {
                          field.onChange(arrayToggle(field.value, "html"));
                        }}
                      />
                      <FormLabel htmlFor="html-checkbox">HTML</FormLabel>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id="ipynb-checkbox"
                        checked={field.value.includes("ipynb")}
                        onCheckedChange={() => {
                          field.onChange(arrayToggle(field.value, "ipynb"));
                        }}
                      />
                      <FormLabel htmlFor="ipynb-checkbox">IPYNB</FormLabel>
                    </div>
                    {/* Disable markdown until we save outputs in the exported markdown */}
                    {/* <div className="flex items-center space-x-2">
                      <Checkbox
                        id="markdown-checkbox"
                        checked={field.value.includes("markdown")}
                        onCheckedChange={() => {
                          field.onChange(arrayToggle(field.value, "markdown"));
                        }}
                      />
                      <label
                        htmlFor="markdown-checkbox"
                        className="cursor-pointer"
                      >
                        Markdown
                      </label>
                    </div> */}
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
              <FormDescription>
                When enabled, marimo will periodically save this notebook in
                your selected formats (HTML, IPYNB) to a folder named{" "}
                <Kbd className="inline">__marimo__</Kbd> next to your notebook
                file.
              </FormDescription>
            </div>
          )}
        />
      </form>
    </Form>
  );
};
