/* Copyright 2026 Marimo. All rights reserved. */

import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowUpDownIcon,
  BracketsIcon,
  ColumnsIcon,
  CombineIcon,
  CopySlashIcon,
  FileJsonIcon,
  FilterIcon,
  FunctionSquareIcon,
  GroupIcon,
  InfoIcon,
  MousePointerSquareDashedIcon,
  PencilIcon,
  PlusIcon,
  ShuffleIcon,
  SquareMousePointerIcon,
  Table2Icon,
  Trash2Icon,
} from "lucide-react";
import React, {
  type PropsWithChildren,
  useEffect,
  useImperativeHandle,
  useMemo,
} from "react";
import { useFieldArray, useForm } from "react-hook-form";
import useEvent from "react-use-event-hook";
import type { z } from "zod";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import {
  ColumnFetchValuesContext,
  ColumnInfoContext,
} from "@/plugins/impl/data-frames/forms/context";
import { Strings } from "@/utils/strings";
import { ZodForm } from "../../../components/forms/form";
import {
  getDefaults,
  getUnionLiteral,
} from "../../../components/forms/form-utils";
import { Button } from "../../../components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../../components/ui/dropdown-menu";
import { Tooltip } from "../../../components/ui/tooltip";
import { cn } from "../../../utils/cn";
import { DATAFRAME_FORM_RENDERERS } from "./forms/renderers";
import {
  type Transformations,
  TransformationsSchema,
  type TransformType,
  TransformTypeSchema,
} from "./schema";
import type { ColumnDataTypes } from "./types";
import { getEffectiveColumns } from "./utils/getEffectiveColumns";

export interface TransformPanelHandle {
  submit: () => void;
}

interface Props {
  columns: ColumnDataTypes;
  initialValue: Transformations;
  onChange: (value: Transformations) => void;
  onInvalidChange: (value: Transformations) => void;
  getColumnValues: (req: { column: string }) => Promise<{
    values: unknown[];
    too_many_values: boolean;
  }>;
  // Column types at each transform step (index 0 = original, index N = after N transforms)
  columnTypesPerStep?: FieldTypesWithExternalType[];
  lazy: boolean;
  ref?: React.Ref<TransformPanelHandle>;
}

export const TransformPanel: React.FC<Props> = ({
  initialValue,
  columns,
  onChange,
  onInvalidChange,
  getColumnValues,
  columnTypesPerStep,
  lazy,
  ref,
}) => {
  const form = useForm<z.infer<typeof TransformationsSchema>>({
    resolver: zodResolver(TransformationsSchema),
    defaultValues: initialValue,
    mode: "onChange",
    reValidateMode: "onChange",
  });
  const { handleSubmit, watch, control, formState } = form;

  const onSubmit = useEvent((values: z.infer<typeof TransformationsSchema>) => {
    onChange(values);
  });

  const onInvalidSubmit = useEvent(
    (values: z.infer<typeof TransformationsSchema>) => {
      onInvalidChange(values);
    },
  );

  const handleApply = useEvent(() => {
    handleSubmit(
      (values) => {
        onSubmit(values);
        // Reset dirty state by setting current values as new default
        // Use keepValues to avoid re-initializing field arrays
        if (lazy) {
          form.reset(values, { keepValues: true });
        }
      },
      () => {
        onInvalidSubmit(form.getValues());
      },
    )();
  });

  useImperativeHandle(ref, () => {
    return {
      submit: handleApply,
    };
  }, []);

  useEffect(() => {
    // If lazy, do not auto-submit on input changes
    if (lazy) {
      return;
    }
    const subscription = watch(() => {
      handleApply();
    });
    return () => subscription.unsubscribe();
  }, [watch, handleApply, lazy]);

  const [selectedTransform, setSelectedTransform] = React.useState<
    number | undefined
  >(initialValue.transforms.length > 0 ? 0 : undefined);

  // TODO: This crashes in latest version of react-hook-form
  const transformsField = useFieldArray({
    control: control,
    name: "transforms",
  });

  const transforms = form.watch("transforms");
  const selectedTransformType =
    selectedTransform === undefined
      ? undefined
      : transforms[selectedTransform]?.type;
  const selectedTransformSchema = TransformTypeSchema.options.find((option) => {
    return getUnionLiteral(option).value === selectedTransformType;
  });

  const effectiveColumns = useMemo(() => {
    return getEffectiveColumns(columns, columnTypesPerStep, selectedTransform);
  }, [columns, transforms, selectedTransform]);

  const handleAddTransform = (transform: z.ZodType) => {
    const next: TransformType = getDefaults(
      transform as z.ZodType<TransformType>,
    );
    const nextIdx = transformsField.fields.length;
    transformsField.append(next);
    setSelectedTransform(nextIdx);
  };

  return (
    <ColumnInfoContext value={effectiveColumns}>
      <ColumnFetchValuesContext value={getColumnValues}>
        <form
          onSubmit={(e) => e.preventDefault()}
          // When lazy, prevent Enter from submitting
          onKeyDown={
            lazy ? (e) => e.key === "Enter" && e.preventDefault() : undefined
          }
          className="relative flex flex-row max-h-[400px] overflow-hidden bg-background"
        >
          <Sidebar
            items={form.watch("transforms")}
            selected={selectedTransform}
            onSelect={(index) => {
              setSelectedTransform(index);
            }}
            onDelete={(index) => {
              transformsField.remove(index);
              const indexBefore = index - 1;
              setSelectedTransform(Math.max(indexBefore, 0));
            }}
            onAdd={handleAddTransform}
          />
          <div className="flex flex-col flex-1 p-4 overflow-auto min-h-[200px] border-l">
            {selectedTransform !== undefined && selectedTransformSchema && (
              <ZodForm
                key={`transforms.${selectedTransform}`}
                form={form}
                schema={selectedTransformSchema}
                path={`transforms.${selectedTransform}`}
                renderers={DATAFRAME_FORM_RENDERERS}
              />
            )}
            {(selectedTransform === undefined || !selectedTransformSchema) && (
              <div className="flex flex-col items-center justify-center grow gap-3">
                <MousePointerSquareDashedIcon className="w-8 h-8  text-muted-foreground" />
                <AddTransformDropdown onAdd={handleAddTransform}>
                  <Button
                    data-testid="marimo-plugin-data-frames-add-transform"
                    variant="text"
                    size="xs"
                  >
                    <div className="text-sm">Select a transform to begin</div>
                  </Button>
                </AddTransformDropdown>
              </div>
            )}
          </div>
          {lazy && (
            <div className="absolute bottom-0 right-0 border-l border-t rounded-tl-sm flex flex-row items-center gap-1 p-1.5 pr-1">
              <Button
                data-testid="marimo-plugin-data-frames-apply"
                variant={formState.isDirty ? "warn" : "outline"}
                size="xs"
                onClick={handleApply}
                className="h-6"
              >
                Apply
              </Button>
              <Tooltip
                delayDuration={100}
                content={
                  <div className="flex flex-col gap-1.5 text-xs text-muted-foreground max-w-96 text-pretty">
                    <p>
                      This dataframe is marked lazy to improve performance.{" "}
                      <span>
                        Click{" "}
                        <span className="px-1 mr-1 rounded border border-border">
                          Apply
                        </span>
                        to apply the transforms.
                      </span>
                    </p>
                    <p>
                      Pass{" "}
                      <code className="bg-muted px-1 py-0.5 rounded-sm">
                        lazy=False
                      </code>{" "}
                      to{" "}
                      <code className="bg-muted px-1 py-0.5 rounded-sm">
                        mo.ui.dataframe
                      </code>{" "}
                      to automatically apply transformations.
                    </p>
                  </div>
                }
              >
                <InfoIcon className="w-3 h-3 text-muted-foreground hover:text-foreground cursor-help" />
              </Tooltip>
            </div>
          )}
        </form>
      </ColumnFetchValuesContext>
    </ColumnInfoContext>
  );
};

interface SidebarProps {
  items: TransformType[];
  selected: number | undefined;
  onSelect: (index: number) => void;
  onDelete: (index: number) => void;
  onAdd: (transform: z.ZodType) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  items,
  selected,
  onAdd,
  onSelect,
  onDelete,
}) => {
  return (
    <div className="flex flex-col overflow-y-hidden w-[180px] shadow-xs h-full">
      <div className="flex flex-col overflow-y-auto grow">
        {items.map((item, idx) => {
          return (
            <div
              key={`${JSON.stringify(item)}-${idx}`}
              onClick={() => {
                onSelect(idx);
              }}
              className={cn(
                "flex flex-row min-h-[40px] items-center px-2 cursor-pointer hover:bg-accent/50 text-sm overflow-hidden hover-actions-parent border border-muted border-l-2 border-l-transparent",
                {
                  "border-l-primary bg-accent text-accent-foreground":
                    selected === idx,
                },
              )}
            >
              <div className="grow text-ellipsis">
                {Strings.startCase(item.type)}
              </div>
              <Trash2Icon
                className="w-3 h-3 hover-action text-muted-foreground hover:text-destructive"
                onClick={(e) => {
                  onDelete(idx);
                  e.stopPropagation();
                }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex flex-row shrink-0">
        <AddTransformDropdown onAdd={onAdd}>
          <Button
            data-testid="marimo-plugin-data-frames-add-transform"
            variant="text"
            className="w-full rounded-none m-0 hover:text-accent-foreground"
            size="xs"
          >
            <PlusIcon className="w-3 h-3 mr-1" />
            Add
          </Button>
        </AddTransformDropdown>
      </div>
    </div>
  );
};

const AddTransformDropdown: React.FC<
  PropsWithChildren<{ onAdd: (transform: z.ZodType) => void }>
> = ({ onAdd, children }) => {
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>{children}</DropdownMenuTrigger>
      <DropdownMenuContent className="w-56">
        <DropdownMenuLabel>Add Transform</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          {Object.values(TransformTypeSchema.options).map((type) => {
            const literal = getUnionLiteral(type);
            const Icon = ICONS[literal.value as TransformType["type"]];
            return (
              <DropdownMenuItem
                key={literal.value}
                onSelect={(evt) => {
                  evt.stopPropagation();
                  onAdd(type);
                }}
              >
                <Icon className="w-3.5 h-3.5 mr-2" />
                <span>{Strings.startCase(literal.value)}</span>
              </DropdownMenuItem>
            );
          })}
          <DropdownMenuItem
            key="_request_"
            onSelect={(evt) => {
              evt.stopPropagation();
              window.open(
                "https://github.com/marimo-team/marimo/issues/new?title=New%20dataframe%20transform:&labels=enhancement&template=feature_request.yaml",
                "_blank",
              );
            }}
          >
            <span className="underline text-primary text-xs cursor-pointer">
              Request a transform
            </span>
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

const ICONS: Record<TransformType["type"], React.FC<{ className?: string }>> = {
  aggregate: FunctionSquareIcon,
  column_conversion: ColumnsIcon,
  filter_rows: FilterIcon,
  group_by: GroupIcon,
  rename_column: PencilIcon,
  select_columns: SquareMousePointerIcon,
  sort_column: ArrowUpDownIcon,
  shuffle_rows: ShuffleIcon,
  sample_rows: CombineIcon,
  explode_columns: BracketsIcon,
  expand_dict: FileJsonIcon,
  unique: CopySlashIcon,
  pivot: Table2Icon,
};
