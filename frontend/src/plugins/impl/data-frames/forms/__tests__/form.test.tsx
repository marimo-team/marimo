/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { ZodForm } from "../form";
import { TransformTypeSchema } from "../../schema";
import { render } from "@testing-library/react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { z } from "zod";
import type { ColumnId } from "../../types";
import { ColumnInfoContext } from "../context";

const ColumnTypes = new Map([
  [0 as ColumnId, "str"],
  [1 as ColumnId, "bool"],
  ["A" as ColumnId, "str"],
  ["B" as ColumnId, "int"],
]);

const Subject = (props: { schema: z.ZodType }) => {
  const form = useForm({
    resolver: zodResolver(props.schema),
    defaultValues: {},
    mode: "onChange",
    reValidateMode: "onChange",
  });
  return (
    <ColumnInfoContext.Provider value={ColumnTypes}>
      <ZodForm form={form} schema={props.schema} />
    </ColumnInfoContext.Provider>
  );
};

describe("renderZodSchema", () => {
  const options = TransformTypeSchema._def.options;
  // Snapshot each form to make sure they don't change unexpectedly
  it.each(options)("should render a form", (schema) => {
    const expected = render(<Subject schema={schema} />);

    expect(expected.asFragment()).toMatchSnapshot();
  });
});
