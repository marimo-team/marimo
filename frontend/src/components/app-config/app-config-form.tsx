/* Copyright 2026 Marimo. All rights reserved. */
import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useId } from "react";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { useAppConfig } from "@/core/config/config";
import { getAppWidths } from "@/core/config/widths";
import { useRequestClient } from "@/core/network/requests";
import { useDebouncedCallback } from "@/hooks/useDebounce";
import { arrayToggle } from "@/utils/arrays";
import {
  type AppConfig,
  AppConfigSchema,
  AppTitleSchema,
} from "../../core/config/config-schema";
import { Checkbox } from "../ui/checkbox";
import { Input } from "../ui/input";
import { ExternalLink } from "../ui/links";
import { NativeSelect } from "../ui/native-select";
import { toast } from "../ui/use-toast";
import { SQL_OUTPUT_SELECT_OPTIONS } from "./common";

const fieldClasses =
  "gap-1 rounded-md hover:bg-muted/50 focus-within:bg-muted/50 hover:ring-8 hover:ring-muted/50 focus-within:ring-8 focus-within:ring-muted/50 [&_input]:mt-1";
const labelClasses = "font-semibold text-muted-foreground";

const FORM_DEBOUNCE = 100; // ms;

export const AppConfigForm: React.FC = () => {
  const config = useAppConfig();
  const { saveAppConfig } = useRequestClient();
  const htmlCheckboxId = useId();
  const ipynbCheckboxId = useId();

  // Create form
  const form = useForm({
    resolver: zodResolver(
      AppConfigSchema as unknown as z.ZodType<unknown, AppConfig>,
    ),
    defaultValues: config,
  });

  // The host document carries the saved config back.
  const onSubmit = async (values: AppConfig) => {
    await saveAppConfig({ config: values });
  };

  const debouncedSubmit = useDebouncedCallback((v: AppConfig) => {
    // The request client reports a failed save, so nothing is left to handle.
    onSubmit(v).catch(() => undefined);
  }, FORM_DEBOUNCE);

  // When width is changed, dispatch a resize event so widgets know to resize
  useEffect(() => {
    window.dispatchEvent(new Event("resize"));
  }, [config.width]);

  return (
    <Form {...form}>
      <form
        onChange={form.handleSubmit(debouncedSubmit)}
        className="flex flex-col gap-3"
      >
        <div className="space-y-1">
          <h2 className="text-base font-semibold">Notebook settings</h2>
          <p className="text-sm text-muted-foreground">
            These settings apply to this notebook only.
          </p>
        </div>

        <div className="flex flex-col gap-4">
          <FormField
            control={form.control}
            name="width"
            render={({ field }) => (
              <FormItem className={fieldClasses}>
                <FormLabel className={labelClasses}>Width</FormLabel>
                <FormControl>
                  <NativeSelect
                    data-testid="app-width-select"
                    onChange={(e) => field.onChange(e.target.value)}
                    value={field.value}
                    disabled={field.disabled}
                    className="mt-1 mb-0 h-7 min-w-32"
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
              <FormItem className={fieldClasses}>
                <FormLabel className={labelClasses}>App title</FormLabel>
                <FormDescription>
                  The title shown in the browser tab.
                </FormDescription>
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
            )}
          />

          <FormField
            control={form.control}
            name="sql_output"
            render={({ field }) => (
              <FormItem className={fieldClasses}>
                <FormLabel className={labelClasses}>SQL output type</FormLabel>
                <FormDescription>
                  The Python type returned by SQL cells. Use <code>native</code>{" "}
                  for large datasets. See the{" "}
                  <ExternalLink href="https://docs.marimo.io/guides/working_with_data/sql">
                    SQL guide
                  </ExternalLink>
                  .
                </FormDescription>
                <FormControl>
                  <NativeSelect
                    data-testid="sql-output-select"
                    onChange={(e) => {
                      field.onChange(e.target.value);
                      toast({
                        title: "Kernel Restart Required",
                        description:
                          "This change requires a kernel restart to take effect.",
                      });
                    }}
                    value={field.value}
                    disabled={field.disabled}
                    className="mt-1 mb-0 h-7 min-w-32"
                  >
                    {SQL_OUTPUT_SELECT_OPTIONS.map((option) => (
                      <option value={option.value} key={option.value}>
                        {option.label}
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
            name="auto_download"
            render={({ field }) => (
              <FormItem className={fieldClasses}>
                <span className="text-sm font-semibold text-muted-foreground">
                  Save cell outputs
                </span>
                <FormDescription>
                  Automatically save cell outputs as HTML or IPYNB in a{" "}
                  <code>__marimo__</code> folder next to this notebook.
                </FormDescription>
                <FormControl>
                  <div className="mt-1 flex gap-4">
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id={htmlCheckboxId}
                        data-testid="html-checkbox"
                        checked={field.value.includes("html")}
                        onCheckedChange={() => {
                          field.onChange(arrayToggle(field.value, "html"));
                        }}
                      />
                      <FormLabel
                        className={labelClasses}
                        htmlFor={htmlCheckboxId}
                      >
                        HTML
                      </FormLabel>
                    </div>
                    <div className="flex items-center space-x-2">
                      <Checkbox
                        id={ipynbCheckboxId}
                        data-testid="ipynb-checkbox"
                        checked={field.value.includes("ipynb")}
                        onCheckedChange={() => {
                          field.onChange(arrayToggle(field.value, "ipynb"));
                        }}
                      />
                      <FormLabel
                        className={labelClasses}
                        htmlFor={ipynbCheckboxId}
                      >
                        IPYNB
                      </FormLabel>
                    </div>
                  </div>
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="border-t" />
          <FormField
            control={form.control}
            name="css_file"
            render={({ field }) => (
              <FormItem className={fieldClasses}>
                <FormLabel className={labelClasses}>Custom CSS</FormLabel>
                <FormDescription>
                  Path to a CSS file for styling this notebook.
                </FormDescription>
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
            )}
          />
          <FormField
            control={form.control}
            name="html_head_file"
            render={({ field }) => (
              <FormItem className={fieldClasses}>
                <FormLabel className={labelClasses}>HTML head</FormLabel>
                <FormDescription>
                  Path to HTML to add to the notebook’s{" "}
                  <code>&lt;head&gt;</code>.
                </FormDescription>
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
            )}
          />
        </div>
      </form>
    </Form>
  );
};
