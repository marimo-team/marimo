/* Copyright 2026 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import React from "react";
import { type FieldValues, useForm } from "react-hook-form";
import type { z } from "zod";
import { type FormRenderer, ZodForm } from "@/components/forms/form";
import { getDefaults } from "@/components/forms/form-utils";
import { Button } from "@/components/ui/button";
import { FormErrorsBanner } from "@/components/ui/form";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { ENV_RENDERER, SecretsProvider } from "./form-renderers";

const RENDERERS: FormRenderer[] = [ENV_RENDERER];

/**
 * Grid layout for provider/database selector buttons.
 */
export const SelectorGrid: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => <div className="grid grid-cols-2 md:grid-cols-3 gap-4">{children}</div>;

/**
 * A colored button tile for selecting a provider/database.
 */
export const SelectorButton: React.FC<{
  name: string;
  color: string;
  icon: React.ReactNode;
  onSelect: () => void;
}> = ({ name, color, icon, onSelect }) => (
  <button
    type="button"
    className="py-3 flex flex-col items-center justify-center gap-1 transition-all hover:scale-105 hover:brightness-110 rounded shadow-sm-solid hover:shadow-md-solid"
    style={{ backgroundColor: color }}
    onClick={onSelect}
  >
    {icon}
    <span className="text-white font-medium text-lg">{name}</span>
  </button>
);

/**
 * Footer with Back/Add buttons and a library picker.
 */
export const ConnectionFormFooter: React.FC<{
  onBack: () => void;
  isValid: boolean;
  libraries: string[];
  preferredLibrary: string;
  onLibraryChange: (library: string) => void;
  displayNames: Record<string, string>;
  libraryLabel?: string;
}> = ({
  onBack,
  isValid,
  libraries,
  preferredLibrary,
  onLibraryChange,
  displayNames,
  libraryLabel = "Preferred library",
}) => (
  <div className="flex gap-2 justify-between">
    <div className="flex gap-2">
      <Button type="button" variant="outline" onClick={onBack}>
        Back
      </Button>
      <Button type="submit" disabled={!isValid}>
        Add
      </Button>
    </div>
    <div>
      <Select value={preferredLibrary} onValueChange={onLibraryChange}>
        <div className="flex flex-col gap-1 items-end">
          <SelectTrigger>
            <SelectValue placeholder="Select a library" />
          </SelectTrigger>
          <span className="text-xs text-muted-foreground">{libraryLabel}</span>
        </div>
        <SelectContent>
          <SelectGroup>
            {libraries.map((library) => (
              <SelectItem key={library} value={library}>
                {displayNames[library] ?? library}
              </SelectItem>
            ))}
          </SelectGroup>
        </SelectContent>
      </Select>
    </div>
  </div>
);

/**
 * Returns a callback that inserts code into a new cell after the last focused cell.
 */
export function useInsertCode() {
  const { createNewCell } = useCellActions();
  const lastFocusedCellId = useLastFocusedCellId();

  return (code: string) => {
    createNewCell({
      code,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
      skipIfCodeExists: true,
    });
  };
}

/**
 * Generic connection form: Zod-driven form with secrets support, a library
 * picker, and Back/Add buttons. Used by both database and storage forms.
 */
export const ConnectionForm = <T extends FieldValues>({
  schema,
  libraries,
  preferredLibrary: initialPreferred,
  displayNames,
  libraryLabel,
  generateCode,
  onSubmit,
  onBack,
}: {
  schema: z.ZodType<T>;
  libraries: string[];
  preferredLibrary: string;
  displayNames: Record<string, string>;
  libraryLabel?: string;
  generateCode: (values: T, library: string) => string;
  onSubmit: () => void;
  onBack: () => void;
}) => {
  const form = useForm<T>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-unnecessary-type-assertion
    defaultValues: getDefaults(schema) as any,
    resolver: zodResolver(schema as unknown as z.ZodType<unknown, T>),
    reValidateMode: "onChange",
  });

  const [preferredLibrary, setPreferredLibrary] =
    React.useState(initialPreferred);
  const insertCode = useInsertCode();

  const handleSubmit = (values: T) => {
    insertCode(generateCode(values, preferredLibrary));
    onSubmit();
  };

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
      <SecretsProvider>
        <ZodForm schema={schema} form={form} renderers={RENDERERS}>
          <FormErrorsBanner />
        </ZodForm>
      </SecretsProvider>
      <ConnectionFormFooter
        onBack={onBack}
        isValid={form.formState.isValid}
        libraries={libraries}
        preferredLibrary={preferredLibrary}
        onLibraryChange={setPreferredLibrary}
        displayNames={displayNames}
        libraryLabel={libraryLabel}
      />
    </form>
  );
};
