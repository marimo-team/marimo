/* Copyright 2024 Marimo. All rights reserved. */

import {
  ChevronDownIcon,
  PowerOffIcon,
  ZapIcon,
  ZapOffIcon,
} from "lucide-react";
import type React from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Switch } from "@/components/ui/switch";
import { useResolvedMarimoConfig, useUserConfig } from "@/core/config/config";
import type { UserConfig } from "@/core/config/config-schema";
import { saveUserConfig } from "@/core/network/requests";
import { isWasm } from "@/core/wasm/utils";
import { cn } from "@/utils/cn";
import { FooterItem } from "../footer-item";

interface RuntimeSettingsProps {
  className?: string;
}

export const RuntimeSettings: React.FC<RuntimeSettingsProps> = ({
  className,
}) => {
  const [userConfig, setUserConfig] = useUserConfig();
  const config = useResolvedMarimoConfig()[0];

  const handleStartupToggle = async (checked: boolean) => {
    const newConfig = {
      ...config,
      runtime: {
        ...config.runtime,
        auto_instantiate: checked,
      },
    };
    await saveUserConfig({ config: newConfig }).then(() =>
      setUserConfig(newConfig),
    );
  };

  const handleCellChangeToggle = async (checked: boolean) => {
    const newUserConfig: UserConfig = {
      ...userConfig,
      runtime: {
        ...userConfig.runtime,
        on_cell_change: checked ? "autorun" : "lazy",
      },
    };
    await saveUserConfig({ config: newUserConfig }).then(() =>
      setUserConfig(newUserConfig),
    );
  };

  const handleModuleReloadChange = async (
    option: "off" | "lazy" | "autorun",
  ) => {
    const newUserConfig: UserConfig = {
      ...userConfig,
      runtime: {
        ...userConfig.runtime,
        auto_reload: option,
      },
    };
    await saveUserConfig({ config: newUserConfig }).then(() =>
      setUserConfig(newUserConfig),
    );
  };

  // Check if all reactivity is disabled
  const allReactivityDisabled =
    !config.runtime.auto_instantiate &&
    config.runtime.on_cell_change === "lazy" &&
    (isWasm() || config.runtime.auto_reload !== "autorun");

  return (
    <div className={cn("flex items-center", className)}>
      {/* Shown on md and above */}
      <div className="hidden md:flex md:items-center">
        <FooterItem
          tooltip={
            config.runtime.auto_instantiate
              ? "Disable autorun on startup"
              : "Enable autorun on startup"
          }
          selected={false}
          onClick={() => handleStartupToggle(!config.runtime.auto_instantiate)}
          data-testid="footer-autorun-startup"
        >
          <div className="font-prose text-sm flex items-center gap-1 whitespace-nowrap">
            <span>on startup: </span>
            {config.runtime.auto_instantiate ? (
              <ZapIcon size={14} />
            ) : (
              <ZapOffIcon size={14} />
            )}
            <span>{config.runtime.auto_instantiate ? "autorun" : "lazy"}</span>
          </div>
        </FooterItem>

        <div className="border-r border-border h-6 mx-1" />

        <FooterItem
          tooltip={
            config.runtime.on_cell_change === "autorun"
              ? "Disable autorun"
              : "Enable autorun"
          }
          selected={false}
          onClick={() =>
            handleCellChangeToggle(config.runtime.on_cell_change !== "autorun")
          }
          data-testid="footer-autorun-cell-change"
        >
          <div className="font-prose text-sm flex items-center gap-1 whitespace-nowrap">
            <span>on cell change: </span>
            {config.runtime.on_cell_change === "autorun" ? (
              <ZapIcon size={14} />
            ) : (
              <ZapOffIcon size={14} />
            )}
            <span>{config.runtime.on_cell_change}</span>
          </div>
        </FooterItem>

        {!isWasm() && (
          <>
            <div className="border-r border-border h-6 mx-1" />
            <FooterItem
              tooltip={null}
              selected={false}
              data-testid="footer-module-reload"
            >
              <DropdownMenu>
                <DropdownMenuTrigger className="font-prose text-sm flex items-center gap-1 whitespace-nowrap">
                  <span>on module change: </span>
                  {config.runtime.auto_reload === "off" && (
                    <PowerOffIcon size={14} />
                  )}
                  {config.runtime.auto_reload === "lazy" && (
                    <ZapOffIcon size={14} />
                  )}
                  {config.runtime.auto_reload === "autorun" && (
                    <ZapIcon size={14} />
                  )}
                  <span>{config.runtime.auto_reload}</span>
                  <ChevronDownIcon size={14} />
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  {["off", "lazy", "autorun"].map((option) => (
                    <DropdownMenuItem
                      key={option}
                      onClick={() =>
                        handleModuleReloadChange(
                          option as "off" | "lazy" | "autorun",
                        )
                      }
                    >
                      {option === "off" && (
                        <PowerOffIcon
                          size={14}
                          className="mr-2 text-muted-foreground"
                        />
                      )}
                      {option === "lazy" && (
                        <ZapOffIcon
                          size={14}
                          className="mr-2 text-muted-foreground"
                        />
                      )}
                      {option === "autorun" && (
                        <ZapIcon
                          size={14}
                          className="mr-2 text-muted-foreground"
                        />
                      )}
                      {option}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            </FooterItem>
          </>
        )}
      </div>

      {/* Shown on small screens */}
      <div className="flex md:hidden">
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <FooterItem
              tooltip="Runtime reactivity"
              selected={false}
              data-testid="footer-runtime-settings"
            >
              <div className="flex items-center gap-1">
                {allReactivityDisabled ? (
                  <ZapOffIcon size={16} className="text-muted-foreground" />
                ) : (
                  <ZapIcon size={16} className="text-amber-500" />
                )}
                <ChevronDownIcon size={14} />
              </div>
            </FooterItem>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-64">
            <DropdownMenuLabel>Runtime reactivity</DropdownMenuLabel>
            <DropdownMenuSeparator />

            {/* On startup toggle */}
            <div className="flex items-center justify-between px-2 py-2">
              <div className="flex items-center space-x-2">
                {config.runtime.auto_instantiate ? (
                  <ZapIcon size={14} className="text-amber-500" />
                ) : (
                  <ZapOffIcon size={14} className="text-muted-foreground" />
                )}
                <div>
                  <div className="text-sm font-medium">On startup</div>
                  <div className="text-xs text-muted-foreground">
                    {config.runtime.auto_instantiate ? "autorun" : "lazy"}
                  </div>
                </div>
              </div>
              <Switch
                checked={config.runtime.auto_instantiate}
                onCheckedChange={handleStartupToggle}
                size="sm"
              />
            </div>

            <DropdownMenuSeparator />

            {/* On cell change toggle */}
            <div className="flex items-center justify-between px-2 py-2">
              <div className="flex items-center space-x-2">
                {config.runtime.on_cell_change === "autorun" ? (
                  <ZapIcon size={14} className="text-amber-500" />
                ) : (
                  <ZapOffIcon size={14} className="text-muted-foreground" />
                )}
                <div>
                  <div className="text-sm font-medium">On cell change</div>
                  <div className="text-xs text-muted-foreground">
                    {config.runtime.on_cell_change}
                  </div>
                </div>
              </div>
              <Switch
                checked={config.runtime.on_cell_change === "autorun"}
                onCheckedChange={handleCellChangeToggle}
                size="sm"
              />
            </div>

            {!isWasm() && (
              <>
                <DropdownMenuSeparator />

                {/* On module change dropdown */}
                <div className="px-2 py-1">
                  <div className="flex items-center space-x-2 mb-2">
                    {config.runtime.auto_reload === "off" && (
                      <PowerOffIcon
                        size={14}
                        className="text-muted-foreground"
                      />
                    )}
                    {config.runtime.auto_reload === "lazy" && (
                      <ZapOffIcon size={14} className="text-muted-foreground" />
                    )}
                    {config.runtime.auto_reload === "autorun" && (
                      <ZapIcon size={14} className="text-amber-500" />
                    )}
                    <div>
                      <div className="text-sm font-medium">
                        On module change
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {config.runtime.auto_reload}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-1">
                    {["off", "lazy", "autorun"].map((option) => (
                      <button
                        key={option}
                        onClick={() =>
                          handleModuleReloadChange(
                            option as "off" | "lazy" | "autorun",
                          )
                        }
                        className={cn(
                          "w-full flex items-center px-2 py-1 text-sm rounded hover:bg-accent",
                          option === config.runtime.auto_reload && "bg-accent",
                        )}
                      >
                        {option === "off" && (
                          <PowerOffIcon size={12} className="mr-2" />
                        )}
                        {option === "lazy" && (
                          <ZapOffIcon size={12} className="mr-2" />
                        )}
                        {option === "autorun" && (
                          <ZapIcon size={12} className="mr-2" />
                        )}
                        <span className="capitalize">{option}</span>
                        {option === config.runtime.auto_reload && (
                          <span className="ml-auto">✓</span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};
