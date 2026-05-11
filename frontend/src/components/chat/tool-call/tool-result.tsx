/* Copyright 2026 Marimo. All rights reserved. */

import { isEmpty } from "lodash-es";
import { InfoIcon } from "lucide-react";
import React from "react";
import { z } from "zod";

// A value worth rendering: drop null/undefined and empty containers
// (`{}`, `[]`), but keep meaningful primitives (`0`, `false`, `""`).
function isUninformative(value: unknown): boolean {
  if (value == null) {
    return true;
  }
  if (typeof value === "object") {
    return isEmpty(value);
  }
  return false;
}

// Zod schema matching the Python SuccessResult dataclass
const SuccessResultSchema = z.looseObject({
  status: z.string().default("success"),
  auth_required: z.boolean().default(false),
  action_url: z.any(),
  next_steps: z.any(),
  meta: z.any(),
  message: z.string().nullish(),
});

type SuccessResult = z.infer<typeof SuccessResultSchema>;

const PrettySuccessResult: React.FC<{ data: SuccessResult }> = ({ data }) => {
  const {
    status,
    auth_required,
    action_url: _action_url,
    meta: _meta,
    next_steps: _next_steps,
    message,
    ...rest
  } = data;

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-muted-foreground">
          Tool Result
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs px-2 py-0.5 bg-(--grass-2) text-(--grass-11) rounded-full font-medium capitalize">
            {status}
          </span>
          {auth_required && (
            <span className="text-xs px-2 py-0.5 bg-(--amber-2) text-(--amber-11) rounded-full">
              Auth Required
            </span>
          )}
        </div>
      </div>

      {message && (
        <div className="flex items-start gap-2">
          <InfoIcon className="h-3 w-3 text-(--blue-11) mt-0.5 shrink-0" />
          <div className="text-xs text-foreground">{message}</div>
        </div>
      )}

      {rest && (
        <div className="space-y-3">
          {Object.entries(rest).map(([key, value]) => {
            if (isUninformative(value)) {
              return null;
            }
            return (
              <div key={key} className="space-y-1.5">
                <span className="text-xs text-muted-foreground">{key}</span>
                <pre className="bg-(--slate-2) p-2 text-muted-foreground border border-(--slate-4) rounded text-xs overflow-auto scrollbar-thin max-h-64">
                  {JSON.stringify(value, null, 2)}
                </pre>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export const ResultRenderer: React.FC<{ result: unknown }> = ({ result }) => {
  const parseResult = SuccessResultSchema.safeParse(result);

  if (parseResult.success) {
    return <PrettySuccessResult data={parseResult.data} />;
  }

  return (
    <div className="text-xs font-medium text-muted-foreground mb-1 max-h-64 overflow-y-auto scrollbar-thin">
      {typeof result === "string" ? result : JSON.stringify(result, null, 2)}
    </div>
  );
};
