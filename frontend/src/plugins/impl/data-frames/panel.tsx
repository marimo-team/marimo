/* Copyright 2024 Marimo. All rights reserved. */
import React, { type PropsWithChildren, useEffect, useMemo } from "react";
import {
  type TransformType,
  TransformTypeSchema,
  type Transformations,
  TransformationsSchema,
} from "./schema";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../../../components/ui/dropdown-menu";
import { Button } from "../../../components/ui/button";
import { zodResolver } from "@hookform/resolvers/zod";
import { useFieldArray, useForm } from "react-hook-form";
import type { z } from "zod";
import { ZodForm } from "../../../components/forms/form";
import {
  getDefaults,
  getUnionLiteral,
} from "../../../components/forms/form-utils";
import {
  ArrowUpDownIcon,
  ColumnsIcon,
  CombineIcon,
  FilterIcon,
  FunctionSquareIcon,
  GroupIcon,
  MousePointerSquareDashedIcon,
  SquareMousePointerIcon,
  PencilIcon,
  PlusIcon,
  ShuffleIcon,
  Trash2Icon,
  BracketsIcon,
  FileJsonIcon,
  CopySlashIcon,
} from "lucide-react";
import { cn } from "../../../utils/cn";
import {
  ColumnFetchValuesContext,
  ColumnInfoContext,
} from "@/plugins/impl/data-frames/forms/context";
import useEvent from "react-use-event-hook";
import type { ColumnDataTypes } from "./types";
import { getUpdatedColumnTypes } from "./utils/getUpdatedColumnTypes";
import { Strings } from "@/utils/strings";
import { DATAFRAME_FORM_RENDERERS } from "./forms/renderers";

interface Props {
  columns: ColumnDataTypes;
  initialValue: Transformations;
  onChange: (value: Transformations) => void;
  onInvalidChange: (value: Transformations) => void;
  getColumnValues: (req: { column: string }) => Promise<{
    values: unknown[];
    too_many_values: boolean;
  }>;
}

export const TransformPanel: React.FC<Props> = ({
  initialValue,
  columns,
  onChange,
  onInvalidChange,
  getColumnValues,
}) => {
  const form = useForm<z.infer<typeof TransformationsSchema>>({
    resolver: zodResolver(TransformationsSchema),
    defaultValues: initialValue,
    mode: "onChange",
    reValidateMode: "onChange",
  });
  const { handleSubmit, watch, control } = form;

  const onSubmit = useEvent((values: z.infer<typeof TransformationsSchema>) => {
    onChange(values);
  });

  const onInvalidSubmit = useEvent(
    (values: z.infer<typeof TransformationsSchema>) => {
      onInvalidChange(values);
    },
  );

  useEffect(() => {
    const subscription = watch(() => {
      handleSubmit(onSubmit, () => {
        onInvalidSubmit(form.getValues());
      })();
    });
    return () => subscription.unsubscribe();
  }, [handleSubmit, watch, onInvalidSubmit, onSubmit, form]);

  const [selectedTransform, setSelectedTransform] = React.useState<
    number | undefined
  >(initialValue.transforms.length > 0 ? 0 : undefined);

  const transformsField = useFieldArray({
    control: control,
    name: "transforms",
  });

  const transforms = form.watch("transforms");
  const selectedTransformType =
    selectedTransform === undefined
      ? undefined
      : transforms[selectedTransform]?.type;
  const selectedTransformSchema = TransformTypeSchema._def.options.find(
    (option) => {
      return getUnionLiteral(option)._def.value === selectedTransformType;
    },
  );

  const effectiveColumns = useMemo(() => {
    const transformsBeforeSelected = transforms.slice(0, selectedTransform);
    return getUpdatedColumnTypes(transformsBeforeSelected, columns);
  }, [columns, transforms, selectedTransform]);

  const handleAddTransform = (transform: z.ZodType) => {
    const next: TransformType = getDefaults(transform);
    const nextIdx = transformsField.fields.length;
    transformsField.append(next);
    setSelectedTransform(nextIdx);
  };

  return (
    <ColumnInfoContext.Provider value={effectiveColumns}>
      <ColumnFetchValuesContext.Provider value={getColumnValues}>
        <form
          onSubmit={(e) => e.preventDefault()}
          className="flex flex-row max-h-[400px] overflow-hidden bg-background"
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
              <div className="flex flex-col items-center justify-center flex-grow gap-3">
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
        </form>
      </ColumnFetchValuesContext.Provider>
    </ColumnInfoContext.Provider>
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
      <div className="flex flex-col overflow-y-auto flex-grow">
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
              <div className="flex-grow text-ellipsis">
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
      <div className="flex flex-row flex-shrink-0">
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
          {Object.values(TransformTypeSchema._def.options).map((type) => {
            const literal = getUnionLiteral(type);
            const Icon = ICONS[literal._def.value as TransformType["type"]];
            return (
              <DropdownMenuItem
                key={literal._def.value}
                onSelect={(evt) => {
                  evt.stopPropagation();
                  onAdd(type);
                }}
              >
                <Icon className="w-3.5 h-3.5 mr-2" />
                <span>{Strings.startCase(literal._def.value)}</span>
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
};
