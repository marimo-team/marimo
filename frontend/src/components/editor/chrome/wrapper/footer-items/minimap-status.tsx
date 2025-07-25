/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { MapIcon } from "lucide-react";
import { FooterItem } from "../footer-item";
import { minimapOpenAtom } from "../minimap-state";

export const MinimapStatusIcon: React.FC = () => {
  const [open, setOpen] = useAtom(minimapOpenAtom);

  return (
    <FooterItem
      tooltip="Toggle Minimap"
      selected={open}
      onClick={() => setOpen((prev) => !prev)}
      data-testid="footer-minimap"
    >
      <MapIcon className="h-4 w-4" />
    </FooterItem>
  );
};
