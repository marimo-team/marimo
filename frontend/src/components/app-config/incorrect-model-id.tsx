/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { AiModelId, type QualifiedModelId } from "@/core/ai/ids/ids";
import { Banner } from "@/plugins/impl/common/error-banner";

interface IncorrectModelIdProps {
  value: string | null | undefined;
  includeSuggestion?: boolean;
}

export const IncorrectModelId: React.FC<IncorrectModelIdProps> = ({
  value,
  includeSuggestion = true,
}) => {
  if (!value) {
    return null;
  }

  // Only incorrect if missing a slash
  if (value.includes("/")) {
    return null;
  }

  // Try to "correct" by guessing provider
  const parsed = AiModelId.parse(value as QualifiedModelId);
  const suggestion = parsed.id;

  return (
    <Banner kind="danger" className="mt-1">
      <span>
        Model id should be in the form{" "}
        <code className="font-bold">provider/model</code>. {value} is missing a
        provider.
      </span>
      <br />
      {includeSuggestion && suggestion && (
        <span>
          Did you mean <code className="font-bold">{suggestion}</code>?
        </span>
      )}
    </Banner>
  );
};
