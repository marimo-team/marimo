/* Copyright 2024 Marimo. All rights reserved. */

import { MapIcon } from "lucide-react";
import { useChromeActions, useChromeState } from "../../state";
import { FooterItem } from "../footer-item";

export const MinimapStatusIcon: React.FC = () => {
  const { isMinimapOpen } = useChromeState();
  const { toggleMinimap } = useChromeActions();

  return (
    <FooterItem
      tooltip="Toggle Minimap"
      selected={isMinimapOpen}
      onClick={() => toggleMinimap()}
      data-testid="footer-minimap"
    >
      <MapIcon className="h-4 w-4" />
    </FooterItem>
  );
};
