/* Copyright 2026 Marimo. All rights reserved. */

import {
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsDownUpIcon,
  ChevronsUpDownIcon,
  ExpandIcon,
} from "lucide-react";
import type React from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import type { CellOutputPosition } from "@/core/config/config-schema";
import { CellChromeItem, CellChromeRail } from "./cell-chrome-rail";
import {
  CELL_CHROME_ICON_CLASS,
  type ChromeRailPlacement,
  chromePlacementKey,
  getOutputChromePlacements,
} from "./chrome-placement";

export interface OutputCollapseChrome {
  canCollapse: boolean;
  isCollapsed: boolean;
  onToggle: () => void;
}

export interface OutputExpandChrome {
  forceExpand?: boolean;
  isOverflowing: boolean;
  isExpanded: boolean;
  onToggle: () => void;
}

export interface OutputFullscreenChrome {
  enabled: boolean;
  onClick: () => void;
}

interface OutputChromeProps {
  outputPosition: CellOutputPosition | undefined;
  collapse?: OutputCollapseChrome;
  expand: OutputExpandChrome;
  fullscreen: OutputFullscreenChrome;
}

type TooltipSide = ChromeRailPlacement["tooltipSide"];

const CollapseButton: React.FC<{
  collapse: OutputCollapseChrome;
  tooltipSide: TooltipSide;
}> = ({ collapse, tooltipSide }) => {
  const Icon = collapse.isCollapsed ? ChevronRightIcon : ChevronDownIcon;
  return (
    <CellChromeItem
      data-testid="collapse-cell-button"
      onClick={collapse.onToggle}
    >
      <Tooltip
        content={collapse.isCollapsed ? "Expand" : "Collapse"}
        side={tooltipSide}
      >
        <span>
          <Icon className={CELL_CHROME_ICON_CLASS} strokeWidth={1.8} />
        </span>
      </Tooltip>
    </CellChromeItem>
  );
};

const ExpandHeightButton: React.FC<{
  expand: OutputExpandChrome;
  tooltipSide: TooltipSide;
}> = ({ expand, tooltipSide }) => {
  const Icon = expand.isExpanded ? ChevronsDownUpIcon : ChevronsUpDownIcon;
  return (
    <CellChromeItem
      data-testid="expand-output-button"
      className={cn(!expand.isExpanded && "hover-action")}
      onClick={expand.onToggle}
    >
      <Tooltip
        content={expand.isExpanded ? "Collapse output" : "Expand output"}
        side={tooltipSide}
      >
        <Icon className={CELL_CHROME_ICON_CLASS} />
      </Tooltip>
    </CellChromeItem>
  );
};

const FullscreenButton: React.FC<{
  fullscreen: OutputFullscreenChrome;
  tooltipSide: TooltipSide;
}> = ({ fullscreen, tooltipSide }) => (
  <Tooltip content="Fullscreen" side={tooltipSide}>
    <CellChromeItem
      data-testid="fullscreen-output-button"
      onClick={fullscreen.onClick}
      onMouseDown={Events.preventFocus}
    >
      <ExpandIcon className={CELL_CHROME_ICON_CLASS} strokeWidth={1.25} />
    </CellChromeItem>
  </Tooltip>
);

interface ChromeControl {
  placement: ChromeRailPlacement;
  node: React.ReactElement;
}

interface ChromeRail {
  placement: ChromeRailPlacement;
  controls: React.ReactElement[];
}

/** Group controls that share a placement into a single rail, keeping order. */
function groupIntoRails(controls: ChromeControl[]): ChromeRail[] {
  const rails = new Map<string, ChromeRail>();
  for (const { placement, node } of controls) {
    const key = chromePlacementKey(placement);
    const rail = rails.get(key);
    if (rail) {
      rail.controls.push(node);
    } else {
      rails.set(key, { placement, controls: [node] });
    }
  }
  return [...rails.values()];
}

/**
 * Output-adjacent controls. Each button has its own placement; buttons that
 * share a placement are stacked in one rail.
 */
export const OutputChrome: React.FC<OutputChromeProps> = ({
  outputPosition,
  collapse,
  expand,
  fullscreen,
}) => {
  const placements = getOutputChromePlacements(outputPosition);

  const controls: ChromeControl[] = [
    fullscreen.enabled && {
      placement: placements.fullscreen,
      node: (
        <FullscreenButton
          key="fullscreen"
          fullscreen={fullscreen}
          tooltipSide={placements.fullscreen.tooltipSide}
        />
      ),
    },
    collapse != null &&
      (collapse.canCollapse || collapse.isCollapsed) && {
        placement: placements.collapse,
        node: (
          <CollapseButton
            key="collapse"
            collapse={collapse}
            tooltipSide={placements.collapse.tooltipSide}
          />
        ),
      },
    (expand.isOverflowing || expand.isExpanded) &&
      !expand.forceExpand && {
        placement: placements.expand,
        node: (
          <ExpandHeightButton
            key="expand"
            expand={expand}
            tooltipSide={placements.expand.tooltipSide}
          />
        ),
      },
  ].filter((control): control is ChromeControl => control !== false);

  if (controls.length === 0) {
    return null;
  }

  return (
    <>
      {groupIntoRails(controls).map((rail) => (
        <CellChromeRail
          key={chromePlacementKey(rail.placement)}
          placement={rail.placement}
        >
          {rail.controls}
        </CellChromeRail>
      ))}
    </>
  );
};
