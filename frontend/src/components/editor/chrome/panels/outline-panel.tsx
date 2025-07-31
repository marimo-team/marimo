/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { ScrollTextIcon } from "lucide-react";
import React, { useMemo } from "react";
import { notebookOutline } from "../../../../core/cells/cells";
import { PanelEmptyState } from "./empty-state";

import "./outline-panel.css";
import { OutlineList } from "./outline/floating-outline";
import {
  findOutlineElements,
  useActiveOutline,
} from "./outline/useActiveOutline";

export const OutlinePanel: React.FC = () => {
  const { items } = useAtomValue(notebookOutline);
  const headerElements = useMemo(() => findOutlineElements(items), [items]);
  const { activeHeaderId, activeOccurrences } =
    useActiveOutline(headerElements);

  if (items.length === 0) {
    return (
      <PanelEmptyState
        title="No outline"
        description="Add markdown headings to your notebook to create an outline."
        icon={<ScrollTextIcon />}
      />
    );
  }

  return (
    <OutlineList
      items={items}
      activeHeaderId={activeHeaderId}
      activeOccurrences={activeOccurrences}
    />
  );
};
