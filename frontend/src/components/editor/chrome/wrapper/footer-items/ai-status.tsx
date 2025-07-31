/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SparklesIcon } from "lucide-react";
import React from "react";
import { useOpenSettingsToTab } from "@/components/app-config/state";
import { aiAtom, aiEnabledAtom } from "@/core/config/config";
import { FooterItem } from "../footer-item";

export const AIStatusIcon: React.FC = () => {
  const ai = useAtomValue(aiAtom);
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const model = ai?.open_ai?.model || "gpt-4-turbo";
  const { handleClick } = useOpenSettingsToTab();

  if (!aiEnabled) {
    return (
      <FooterItem
        tooltip="Assist is disabled"
        selected={false}
        onClick={() => handleClick("ai")}
        data-testid="footer-ai-disabled"
      >
        <SparklesIcon className="h-4 w-4 opacity-60" />
      </FooterItem>
    );
  }

  return (
    <FooterItem
      tooltip={
        <>
          <b>Assist model:</b> {model}
        </>
      }
      onClick={() => handleClick("ai")}
      selected={false}
      data-testid="footer-ai-enabled"
    >
      <SparklesIcon className="h-4 w-4" />
    </FooterItem>
  );
};
