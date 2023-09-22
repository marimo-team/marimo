/* Copyright 2023 Marimo. All rights reserved. */
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "@/components/ui/form";
import { AppConfig, AppConfigSchema } from "../../core/config/config";
import { toast } from "../ui/use-toast";
import { useAppConfig } from "@/core/state/config";
import { Switch } from "@/components/ui/switch";
import { saveAppConfig } from "@/core/network/requests";
import { SettingTitle } from "./common";

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

  return (
    <Form {...form}>
      <form
        onChange={form.handleSubmit(onSubmit)}
        className="flex flex-col gap-4"
      >
        <SettingTitle>Application config</SettingTitle>
        <FormField
          control={form.control}
          name="width"
          render={({ field }) => (
            <FormItem className="flex flex-row items-center space-x-2 space-y-0">
              <FormControl>
                <Switch
                  checked={field.value === "full"}
                  size="sm"
                  onCheckedChange={(checked) => {
                    return field.onChange(checked === true ? "full" : "normal");
                  }}
                />
              </FormControl>
              <FormLabel className="font-normal">Full-width</FormLabel>
            </FormItem>
          )}
        />
      </form>
    </Form>
  );
};
