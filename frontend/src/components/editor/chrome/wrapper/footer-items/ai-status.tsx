/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { useAtomValue } from "jotai";
import { aiAtom, aiEnabledAtom } from "@/core/config/config";
import { SparklesIcon } from "lucide-react";
import { FooterItem } from "../footer-item";
import { useOpenSettingsToTab } from "@/components/app-config/state";

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
    >
      <SparklesIcon className="h-4 w-4" />
    </FooterItem>
  );
};
