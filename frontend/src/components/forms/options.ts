/* Copyright 2024 Marimo. All rights reserved. */
export interface FieldOptions {
  label?: string;
  description?: string;
  placeholder?: string;
  disabled?: boolean;
  hidden?: boolean;
  direction?: "row" | "column" | "two-columns";
  /**
   * Only valid for string fields
   */
  inputType?:
    | "password"
    | "text"
    | "number"
    | "checkbox"
    | "select"
    | "textarea";
  special?:
    | "column_id"
    | "random_number_button"
    | "column_type"
    | "radio_group"
    | "column_filter"
    | "text_area_multiline"
    | "column_values"
    | "date"
    | "datetime"
    | "time";
  /**
   * Only show options that match the regex
   */
  optionRegex?: string;
}

// eslint-disable-next-line @typescript-eslint/no-redeclare
export const FieldOptions = {
  of(options: FieldOptions): string {
    return JSON.stringify(options);
  },
  parse(options: string | undefined): FieldOptions {
    if (!options) {
      return {};
    }
    try {
      return JSON.parse(options) as FieldOptions;
    } catch {
      return {
        label: options,
      };
    }
  },
};

// Random number between 0 and 100_000
export function randomNumber(): number {
  return Math.floor(Math.random() * 100_000);
}
