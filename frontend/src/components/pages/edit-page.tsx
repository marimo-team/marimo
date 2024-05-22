/* Copyright 2024 Marimo. All rights reserved. */
import { EditApp } from "@/core/edit-app";
import { AppChrome } from "../editor/chrome/wrapper/app-chrome";
import { CommandPalette } from "../editor/controls/command-palette";
import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { useDebugMounting } from "@/hooks/debug";

interface Props {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

const EditPage = (props: Props) => {
  useDebugMounting("EditPage");
  return (
    <AppChrome>
      <EditApp {...props} />
      <CommandPalette />
    </AppChrome>
  );
};

export default EditPage;
