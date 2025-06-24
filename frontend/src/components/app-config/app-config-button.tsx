/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { SettingsIcon } from "lucide-react";
import { AppConfigForm } from "@/components/app-config/app-config-form";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  getConnectionTooltip,
  isAppInteractionDisabled,
} from "@/core/websocket/connection-utils";
import type { WebSocketState } from "@/core/websocket/types";
import { Button as EditorButton } from "../editor/inputs/Inputs";
import { Button } from "../ui/button";
import { Dialog, DialogContent, DialogTrigger } from "../ui/dialog";
import { Tooltip } from "../ui/tooltip";
import { settingDialogAtom } from "./state";
import { UserConfigForm } from "./user-config-form";

interface Props {
  showAppConfig?: boolean;
  connectionState: WebSocketState;
}

export const ConfigButton: React.FC<Props> = ({
  showAppConfig = true,
  connectionState,
}) => {
  const [settingDialog, setSettingDialog] = useAtom(settingDialogAtom);
  const isDisabled = isAppInteractionDisabled(connectionState);
  const tooltipContent = isDisabled
    ? getConnectionTooltip(connectionState)
    : "Settings";

  const button = (
    <EditorButton
      aria-label="Config"
      data-testid="app-config-button"
      shape="circle"
      size="small"
      className="h-[27px] w-[27px]"
      color={isDisabled ? "disabled" : "hint-green"}
    >
      <Tooltip content={tooltipContent}>
        <SettingsIcon strokeWidth={1.8} />
      </Tooltip>
    </EditorButton>
  );

  const userSettingsDialog = (
    <DialogContent className="w-[80vw] h-[70vh] overflow-hidden sm:max-w-5xl top-[15vh] p-0">
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
      <Popover>
        <PopoverTrigger asChild={true}>{button}</PopoverTrigger>
        <PopoverContent
          className="w-[650px] overflow-auto max-h-[80vh] max-w-[80vw]"
          align="end"
          side="bottom"
          // prevent focus outside to hack around a bug in which
          // interacting with buttons closes the popover ...
          onFocusOutside={(evt) => evt.preventDefault()}
        >
          <AppConfigForm />
          <div className="h-px bg-border my-2" />
          <Button
            onClick={() => setSettingDialog(true)}
            variant="link"
            className="px-0"
          >
            <SettingsIcon strokeWidth={1.8} className="w-4 h-4 mr-2" />
            User settings
          </Button>
        </PopoverContent>
      </Popover>
      <Dialog open={settingDialog} onOpenChange={setSettingDialog}>
        {userSettingsDialog}
      </Dialog>
    </>
  );
};
