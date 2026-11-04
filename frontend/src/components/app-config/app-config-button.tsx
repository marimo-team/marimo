/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { ArrowRightIcon, SettingsIcon } from "lucide-react";
import { useState } from "react";
import { AppConfigForm } from "@/components/app-config/app-config-form";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button as EditorButton } from "../editor/inputs/Inputs";
import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";
import { Tooltip } from "../ui/tooltip";
import { settingDialogAtom } from "./state";
import { UserConfigForm } from "./user-config-form";

interface Props {
  showAppConfig?: boolean;
  disabled?: boolean;
  tooltip?: string;
}

export const ConfigButton: React.FC<Props> = ({
  showAppConfig = true,
  disabled = false,
  tooltip = "Settings",
}) => {
  const [settingDialog, setSettingDialog] = useAtom(settingDialogAtom);
  const [popoverOpen, setPopoverOpen] = useState(false);

  const button = (
    <EditorButton
      aria-label="Config"
      data-testid="app-config-button"
      shape="circle"
      size="small"
      className="h-[27px] w-[27px]"
      disabled={disabled}
      color={disabled ? "disabled" : "hint-green"}
    >
      <Tooltip content={tooltip}>
        <SettingsIcon strokeWidth={1.8} />
      </Tooltip>
    </EditorButton>
  );

  const userSettingsDialog = (
    <DialogContent className="flex flex-col gap-0 w-[94vw] h-[90vh] overflow-hidden sm:max-w-5xl top-[5vh] p-0 font-prose">
      <div className="border-b px-6 py-4 pr-12">
        <DialogTitle className="text-base font-semibold">
          User settings
        </DialogTitle>
      </div>
      <UserConfigForm />
    </DialogContent>
  );

  if (!showAppConfig) {
    return (
      <Dialog open={settingDialog} onOpenChange={setSettingDialog}>
        <DialogTrigger>{button}</DialogTrigger>
        {userSettingsDialog}
      </Dialog>
    );
  }

  return (
    <>
      <Popover open={popoverOpen} onOpenChange={setPopoverOpen}>
        <PopoverTrigger asChild={true}>{button}</PopoverTrigger>
        <PopoverContent
          className="flex w-[440px] max-w-[calc(100vw-2rem)] max-h-[80vh] flex-col overflow-hidden p-0 font-prose"
          align="end"
          side="bottom"
          // prevent focus outside to hack around a bug in which
          // interacting with buttons closes the popover ...
          onFocusOutside={(evt) => evt.preventDefault()}
        >
          <div className="shrink-0 border-b p-1.5">
            <Button
              onClick={() => {
                setPopoverOpen(false);
                setSettingDialog(true);
              }}
              variant="ghost"
              className="h-auto w-full justify-between gap-3 px-2.5 py-2 text-left"
            >
              <span className="font-semibold">User settings</span>
              <span className="ml-auto text-xs font-normal text-muted-foreground">
                For all notebooks
              </span>
              <ArrowRightIcon className="h-4 w-4 shrink-0 text-muted-foreground" />
            </Button>
          </div>
          <div className="min-h-0 overflow-y-auto p-4">
            <AppConfigForm />
          </div>
        </PopoverContent>
      </Popover>
      <Dialog open={settingDialog} onOpenChange={setSettingDialog}>
        {userSettingsDialog}
      </Dialog>
    </>
  );
};
