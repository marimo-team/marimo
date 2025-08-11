/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Banner } from "@/plugins/impl/common/error-banner";
import { AiModelId, type QualifiedModelId } from "@/utils/ai/ids";

interface IncorrectModelIdProps {
  value: string | null | undefined;
}

export const IncorrectModelId: React.FC<IncorrectModelIdProps> = ({
  value,
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
      {suggestion && (
        <span>
          Did you mean <code className="font-bold">{suggestion}</code>?
        </span>
      )}
    </Banner>
  );
};
