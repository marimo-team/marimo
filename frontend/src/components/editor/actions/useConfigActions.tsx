/* Copyright 2024 Marimo. All rights reserved. */

import { useAppConfig, useResolvedMarimoConfig } from "@/core/config/config";
import type { AppConfig, UserConfig } from "@/core/config/config-schema";
import { getAppWidths } from "@/core/config/widths";
import { saveAppConfig, saveUserConfig } from "@/core/network/requests";
import { useTheme } from "@/theme/useTheme";
import type { ActionButton } from "./types";

export function useConfigActions() {
  const { theme } = useTheme();
  const [config, setConfig] = useResolvedMarimoConfig();
  const [appConfig, setAppConfig] = useAppConfig();

  const handleUserConfig = async (values: UserConfig) => {
    await saveUserConfig({ config: values }).then(() => {
      setConfig(values);
    });
  };

  const handleAppConfig = async (values: AppConfig) => {
    await saveAppConfig({ config: values }).then(() => {
      setAppConfig(values);
    });
  };

  const actions: ActionButton[] = [
    ...getAppWidths()
      .filter((width) => width !== appConfig.width)
      .map((width) => ({
        label: `App config > Set width=${width}`,
        handle: () => {
          handleAppConfig({
            ...appConfig,
            width: width,
          });
        },
      })),
    {
      label: "Config > Toggle dark mode",
      handle: () => {
        handleUserConfig({
          ...config,
          display: {
            // We don't use the config from the setting since
            // we want to resolve 'system' to it's current value.
            ...config.display,
            theme: theme === "dark" ? "light" : "dark",
          },
        });
      },
    },
    {
      label: "Config > Switch keymap to VIM",
      hidden: config.keymap.preset === "vim",
      handle: () => {
        handleUserConfig({
          ...config,
          keymap: {
            ...config.keymap,
            preset: "vim",
          },
        });
      },
    },
    {
      // Adding VIM here to make it easy to search
      label: "Config > Switch keymap to default (current: VIM)",
      hidden: config.keymap.preset === "default",
      handle: () => {
        handleUserConfig({
          ...config,
          keymap: {
            ...config.keymap,
            preset: "default",
          },
        });
      },
    },
    {
      label: "Config > Disable GitHub Copilot",
      handle: () => {
        handleUserConfig({
          ...config,
          completion: {
            ...config.completion,
            copilot: false,
          },
        });
      },
      hidden: config.completion.copilot !== "github",
    },
    {
      label: "Config > Enable GitHub Copilot",
      handle: () => {
        handleUserConfig({
          ...config,
          completion: {
            ...config.completion,
            copilot: "github",
          },
        });
      },
      hidden: config.completion.copilot === "github",
    },
    {
      label: "Config > Disable reference highlighting",
      hidden: !config.display.reference_highlighting,
      handle: () => {
        handleUserConfig({
          ...config,
          display: {
            ...config.display,
            reference_highlighting: false,
          },
        });
      },
    },
    {
      label: "Config > Enable reference highlighting",
      hidden: config.display.reference_highlighting,
      handle: () => {
        handleUserConfig({
          ...config,
          display: {
            ...config.display,
            reference_highlighting: true,
          },
        });
      },
    },
  ];

  return actions.filter((a) => !a.hidden);
}
