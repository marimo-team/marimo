/* Copyright 2024 Marimo. All rights reserved. */

import { ControlButton } from "@xyflow/react";
import { useAtom } from "jotai";
import { HandIcon, MousePointerIcon, SettingsIcon } from "lucide-react";
import React, { memo } from "react";
import useEvent from "react-use-event-hook";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Switch } from "@/components/ui/switch";
import { canvasSettingsAtom } from "../state";

// Constants
const INTERACTION_MODES = {
  pointer: {
    value: "pointer" as const,
    label: "Pointer (Selection)",
    icon: MousePointerIcon,
  },
  hand: {
    value: "hand" as const,
    label: "Hand (Move)",
    icon: HandIcon,
  },
} as const;

/**
 * Interaction mode control
 */
const InteractionModeControlComponent: React.FC = () => {
  const [settings, setSettings] = useAtom(canvasSettingsAtom);

  const updateInteractionMode = useEvent((mode: "pointer" | "hand") => {
    setSettings((prev) => ({ ...prev, interactionMode: mode }));
  });

  const currentMode = settings.interactionMode;
  const currentModeConfig = INTERACTION_MODES[currentMode];
  const CurrentIcon = currentModeConfig.icon;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <ControlButton title={currentModeConfig.label}>
          <CurrentIcon className="h-4 w-4" />
        </ControlButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right">
        <DropdownMenuRadioGroup
          value={currentMode}
          onValueChange={(value) =>
            updateInteractionMode(value as "pointer" | "hand")
          }
        >
          {Object.values(INTERACTION_MODES).map((modeConfig) => {
            const ModeIcon = modeConfig.icon;
            return (
              <DropdownMenuRadioItem
                key={modeConfig.value}
                value={modeConfig.value}
              >
                <ModeIcon className="h-4 w-4 mr-2" />
                {modeConfig.label}
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const InteractionModeControl = memo(InteractionModeControlComponent);
InteractionModeControl.displayName = "InteractionModeControl";

/**
 * Canvas controls that integrate with React Flow's default Controls component
 */
const CanvasControlsComponent: React.FC = () => {
  const [settings, setSettings] = useAtom(canvasSettingsAtom);

  const updateSetting = useEvent(
    <K extends keyof typeof settings>(key: K, value: (typeof settings)[K]) => {
      setSettings((prev) => ({ ...prev, [key]: value }));
    },
  );

  return (
    <>
      <InteractionModeControl />
      <Popover>
        <PopoverTrigger asChild>
          <ControlButton title="Canvas settings">
            <SettingsIcon className="h-4 w-4" />
          </ControlButton>
        </PopoverTrigger>
        <PopoverContent side="right" className="w-64" align="end">
          <div className="space-y-4">
            <h4 className="font-medium text-sm">Canvas Settings</h4>

            {/* Grid Size */}
            {/* <div className="space-y-2">
              <Label htmlFor="grid-size" className="text-sm">
                Grid Size: {settings.gridSize}px
              </Label>
              <Slider
                id="grid-size"
                min={10}
                max={50}
                step={5}
                value={[settings.gridSize]}
                valueMap={(v) => v}
                onValueChange={([value]) => updateSetting("gridSize", value)}
              />
            </div> */}

            {/* Snap to Grid */}
            <div className="flex items-center justify-between">
              <Label htmlFor="snap-grid" className="text-sm cursor-pointer">
                Snap to Grid
              </Label>
              <Switch
                id="snap-grid"
                checked={settings.snapToGrid}
                onCheckedChange={(checked) =>
                  updateSetting("snapToGrid", checked)
                }
              />
            </div>

            {/* Show Minimap */}
            <div className="flex items-center justify-between">
              <Label htmlFor="show-minimap" className="text-sm cursor-pointer">
                Show Minimap
              </Label>
              <Switch
                id="show-minimap"
                checked={settings.showMinimap}
                onCheckedChange={(checked) =>
                  updateSetting("showMinimap", checked)
                }
              />
            </div>

            {/* Data Flow Direction */}
            <div className="flex items-center justify-between">
              <Label htmlFor="data-flow" className="text-sm cursor-pointer">
                Data Flow
              </Label>
              <Switch
                id="data-flow"
                checked={settings.dataFlow === "left-right"}
                onCheckedChange={(checked) =>
                  updateSetting("dataFlow", checked ? "left-right" : "top-down")
                }
              />
              <span className="text-xs text-muted-foreground ml-2">
                {settings.dataFlow === "left-right" ? "L→R" : "T↓B"}
              </span>
            </div>

            {/* Debug Mode */}
            <div className="flex items-center justify-between">
              <Label htmlFor="debug-mode" className="text-sm cursor-pointer">
                Debug Mode
              </Label>
              <Switch
                id="debug-mode"
                checked={settings.debug}
                onCheckedChange={(checked) => updateSetting("debug", checked)}
              />
            </div>
          </div>
        </PopoverContent>
      </Popover>
    </>
  );
};

export const CanvasControls = memo(CanvasControlsComponent);
CanvasControls.displayName = "CanvasControls";
