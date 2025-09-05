/* Copyright 2024 Marimo. All rights reserved. */

import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { EditApp } from "@/core/edit-app";
import { CommandPalette } from "../components/editor/controls/command-palette";

interface Props {
  userConfig: UserConfig;
  appConfig: AppConfig;
}

const OSONotebookEditPage = (props: Props) => {
  return (
    <>
      <EditApp {...props} />
      <CommandPalette />
    </>
  );
};

export default OSONotebookEditPage;
