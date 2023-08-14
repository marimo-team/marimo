/* Copyright 2023 Marimo. All rights reserved. */
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "../../editor/inputs/Inputs";
import { SettingsIcon } from "lucide-react";
import { UserConfigForm } from "./user-config-form";
import { Tooltip } from "../ui/tooltip";

export const AppConfigButton = () => {
  return (
    <Popover>
      <PopoverTrigger asChild={true}>
        <Button
          aria-label="Config"
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
      <PopoverContent className="w-80" align="end" side="bottom">
        <UserConfigForm />
      </PopoverContent>
    </Popover>
  );
};
