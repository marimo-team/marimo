/* Copyright 2024 Marimo. All rights reserved. */
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "../editor/inputs/Inputs";
import { SettingsIcon } from "lucide-react";
import { UserConfigForm } from "./user-config-form";
import { Tooltip } from "../ui/tooltip";
import { AppConfigForm } from "@/components/app-config/app-config-form";

export const AppConfigButton = () => {
  return (
    <Popover>
      <PopoverTrigger asChild={true}>
        <Button
          aria-label="Config"
          data-testid="app-config-button"
          shape="circle"
          size="small"
          className="h-[27px] w-[27px]"
          color="hint-green"
        >
          <Tooltip content="Settings">
            <SettingsIcon strokeWidth={1.8} />
          </Tooltip>
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 h-[90vh] overflow-auto"
        align="end"
        side="bottom"
        // prevent focus outside to hack around a bug in which
        // interacting with buttons closes the popover ...
        onFocusOutside={(evt) => evt.preventDefault()}
      >
        <AppConfigForm />
        <div className="h-px bg-border my-4" />
        <UserConfigForm />
      </PopoverContent>
    </Popover>
  );
};
