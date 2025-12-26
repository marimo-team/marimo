/* Copyright 2026 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import { render } from "@testing-library/react";
import { type FieldValues, useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import type { z } from "zod";
import { getUnionLiteral } from "@/components/forms/form-utils";
import { Objects } from "@/utils/objects";
import { ZodForm } from "../../../../../components/forms/form";
import { column_id, column_id_array, TransformTypeSchema } from "../../schema";
import type { ColumnId } from "../../types";
import { ColumnInfoContext } from "../context";
import { DATAFRAME_FORM_RENDERERS } from "../renderers";

const ColumnTypes = new Map([
  [0 as ColumnId, "str"],
  [1 as ColumnId, "bool"],
  ["A" as ColumnId, "str"],
  ["B" as ColumnId, "int"],
]);

const Subject = (props: { schema: z.ZodType<unknown, FieldValues> }) => {
  const form = useForm({
    resolver: zodResolver(props.schema),
    defaultValues: {},
    mode: "onChange",
    reValidateMode: "onChange",
  });
  return (
    <ColumnInfoContext.Provider value={ColumnTypes}>
      <ZodForm
        form={form}
        schema={props.schema}
        renderers={DATAFRAME_FORM_RENDERERS}
      />
    </ColumnInfoContext.Provider>
  );
};

describe("renderZodSchema", () => {
  // Snapshot each form to make sure they don't change unexpectedly
  const options = Objects.keyBy(
    [...TransformTypeSchema.options],
    (z) => getUnionLiteral(z).value,
  );
  it.each(
    Object.entries(options),
  )("should render a form %s", (name, schema: z.ZodType<
    unknown,
    FieldValues
  >) => {
    const expected = render(<Subject schema={schema} />);

    expect(expected.asFragment()).toMatchSnapshot();
  });
});

const options = [
  ["column_id", column_id],
  ["column_id_array", column_id_array],
  ["column_id_dot_array", column_id.array()],
  ["column_id_optional", column_id.optional()],
] as const;

it.each(options)("renders custom forms %s", (key, schema) => {
  const expected = render(
    <Subject schema={schema as z.ZodType<unknown, FieldValues>} />,
  );
  expect(expected.asFragment()).toMatchSnapshot();
});
