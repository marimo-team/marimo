/* Copyright 2026 Marimo. All rights reserved. */

import {
  CodeIcon,
  FileIcon,
  FileTextIcon,
  GlobeIcon,
  ImageIcon,
  type LucideIcon,
  NotebookIcon,
} from "lucide-react";
import { type ComponentType, type PropsWithChildren, useId } from "react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  IPYNB_SORT_MODES,
  MARKDOWN_FLAVORS,
  PDF_PRESETS,
  SCRIPT_TYPES,
  type ExportFormat,
  type ExportOptions,
  type MarkdownFlavor,
} from "./state";

export interface FormatOptionsProps {
  options: ExportOptions;
  updateOptions: UpdateExportOptions;
  disabled: boolean;
}

export type UpdateExportOptions = <Format extends keyof ExportOptions>(
  format: Format,
  options: Partial<ExportOptions[Format]>,
) => void;

interface Choice<Value extends string> {
  value: Value;
  label: string;
  description: string;
}

type ChoiceDetails = Omit<Choice<string>, "value">;

function defineChoices<Value extends string>(
  values: readonly Value[],
  details: Record<Value, ChoiceDetails>,
): readonly Choice<Value>[] {
  return values.map((value) => ({ value, ...details[value] }));
}

type MarkdownFormat = MarkdownFlavor | "automatic";
const MARKDOWN_FORMATS: readonly MarkdownFormat[] = [
  "automatic",
  ...MARKDOWN_FLAVORS,
];
const MARKDOWN_FLAVOR_OPTIONS = defineChoices(MARKDOWN_FORMATS, {
  automatic: {
    label: "Automatic",
    description:
      "Chooses a format from the notebook filename. Defaults to Markdown (.md).",
  },
  pymdown: {
    label: "Markdown (.md)",
    description: "Creates a .md file with Python code blocks.",
  },
  qmd: {
    label: "Quarto (.qmd)",
    description: "Creates a .qmd file for Quarto.",
  },
  mystmd: {
    label: "MyST (.myst.md)",
    description: "Creates a .myst.md file for MyST.",
  },
  mdx: {
    label: "MDX (.mdx)",
    description: "Creates a .mdx file for MDX.",
  },
});

const IPYNB_SORT_OPTIONS = defineChoices(IPYNB_SORT_MODES, {
  "top-down": {
    label: "Top to bottom",
    description: "Keeps cells in the same order as this notebook.",
  },
  topological: {
    label: "Dependency order",
    description:
      "Reorders cells so each cell appears after the cells it depends on.",
  },
});

const PDF_PRESET_OPTIONS = defineChoices(PDF_PRESETS, {
  document: {
    label: "Document",
    description: "Creates pages for reading or printing.",
  },
  slides: {
    label: "Slides",
    description: "Creates presentation slides from the notebook.",
  },
});

const PDF_RENDERERS = ["browser", "latex"] as const;
const PDF_RENDERER_OPTIONS = defineChoices(PDF_RENDERERS, {
  browser: {
    label: "Browser",
    description:
      "Uses browser rendering to preserve the notebook's visual output.",
  },
  latex: {
    label: "LaTeX first",
    description:
      "Uses Pandoc and TeX when available, then falls back to browser rendering.",
  },
});

const SCRIPT_TYPE_OPTIONS = defineChoices(SCRIPT_TYPES, {
  source: {
    label: "Notebook source",
    description:
      "Downloads the saved notebook source for continued editing in marimo.",
  },
  flat: {
    label: "Flat script",
    description: "Reorders cells so the Python script runs from top to bottom.",
  },
});

interface FormatDefinition {
  label: string;
  actionLabel: string;
  description: string;
  Icon: LucideIcon;
  Options: ComponentType<FormatOptionsProps>;
}

export const FORMAT_DEFINITIONS: Record<ExportFormat, FormatDefinition> = {
  html: {
    label: "HTML",
    actionLabel: "Export HTML",
    description: "Save the current notebook as an HTML page.",
    Icon: GlobeIcon,
    Options: HTMLFormatOptions,
  },
  markdown: {
    label: "Markdown",
    actionLabel: "Export Markdown",
    description:
      "Save code and text in a Markdown-based file. Cell outputs are not included.",
    Icon: FileTextIcon,
    Options: MarkdownFormatOptions,
  },
  ipynb: {
    label: "Jupyter",
    actionLabel: "Export Jupyter notebook",
    description: "Open the notebook in Jupyter and other compatible tools.",
    Icon: NotebookIcon,
    Options: IPYNBFormatOptions,
  },
  pdf: {
    label: "PDF",
    actionLabel: "Export PDF",
    description: "Save the notebook as a PDF for printing or sharing.",
    Icon: FileIcon,
    Options: PDFFormatOptions,
  },
  script: {
    label: "Python",
    actionLabel: "Export flat script",
    description: "Save the notebook as a Python file.",
    Icon: CodeIcon,
    Options: ScriptFormatOptions,
  },
  png: {
    label: "PNG",
    actionLabel: "Export PNG",
    description: "Capture the current app view as an image.",
    Icon: ImageIcon,
    Options: NoFormatOptions,
  },
};

function HTMLFormatOptions({
  options,
  updateOptions,
  disabled,
}: FormatOptionsProps) {
  return (
    <OptionsGroup>
      <SwitchOption
        label="Include code"
        descriptions={{
          checked: "Includes code cells in the webpage.",
          unchecked: "Leaves code cells out of the webpage.",
        }}
        checked={options.html.includeCode}
        disabled={disabled}
        onCheckedChange={(includeCode) =>
          updateOptions("html", { includeCode })
        }
      />
    </OptionsGroup>
  );
}

function MarkdownFormatOptions({
  options,
  updateOptions,
  disabled,
}: FormatOptionsProps) {
  return (
    <OptionsGroup>
      <SelectOption
        label="Format"
        value={options.markdown.flavor ?? "automatic"}
        disabled={disabled}
        onValueChange={(value) =>
          updateOptions("markdown", {
            flavor: value === "automatic" ? null : value,
          })
        }
        options={MARKDOWN_FLAVOR_OPTIONS}
      />
    </OptionsGroup>
  );
}

function IPYNBFormatOptions({
  options,
  updateOptions,
  disabled,
}: FormatOptionsProps) {
  return (
    <OptionsGroup>
      <RadioOption
        label="Cell order"
        value={options.ipynb.sortMode}
        disabled={disabled}
        onValueChange={(sortMode) => updateOptions("ipynb", { sortMode })}
        options={IPYNB_SORT_OPTIONS}
      />
      <SwitchOption
        label="Include outputs"
        descriptions={{
          checked: "Keeps the outputs currently shown in the notebook.",
          unchecked: "Leaves cell outputs out of the Jupyter notebook.",
        }}
        checked={options.ipynb.includeOutputs}
        disabled={disabled}
        onCheckedChange={(includeOutputs) =>
          updateOptions("ipynb", { includeOutputs })
        }
      />
    </OptionsGroup>
  );
}

function PDFFormatOptions({
  options,
  updateOptions,
  disabled,
}: FormatOptionsProps) {
  return (
    <OptionsGroup>
      <RadioOption
        label="Layout"
        value={options.pdf.preset}
        disabled={disabled}
        onValueChange={(preset) => updateOptions("pdf", { preset })}
        options={PDF_PRESET_OPTIONS}
      />
      <SwitchOption
        label="Include code"
        descriptions={{
          checked: "Includes code cells in the PDF.",
          unchecked: "Leaves code cells out of the PDF.",
        }}
        checked={options.pdf.includeInputs}
        disabled={disabled}
        onCheckedChange={(includeInputs) =>
          updateOptions("pdf", { includeInputs })
        }
      />
      <SwitchOption
        label="Include outputs"
        descriptions={{
          checked: "Keeps the outputs currently shown in the notebook.",
          unchecked: "Leaves cell outputs out of the PDF.",
        }}
        checked={options.pdf.includeOutputs}
        disabled={disabled}
        onCheckedChange={(includeOutputs) =>
          updateOptions("pdf", { includeOutputs })
        }
      />
      {options.pdf.preset === "document" ? (
        <RadioOption
          label="Method"
          value={options.pdf.webpdf ? "browser" : "latex"}
          disabled={disabled}
          onValueChange={(renderer) =>
            updateOptions("pdf", { webpdf: renderer === "browser" })
          }
          options={PDF_RENDERER_OPTIONS}
        />
      ) : null}
    </OptionsGroup>
  );
}

function ScriptFormatOptions({
  options,
  updateOptions,
  disabled,
}: FormatOptionsProps) {
  return (
    <OptionsGroup>
      <RadioOption
        label="Format"
        value={options.script.type}
        disabled={disabled}
        onValueChange={(type) => updateOptions("script", { type })}
        options={SCRIPT_TYPE_OPTIONS}
      />
    </OptionsGroup>
  );
}

function NoFormatOptions() {
  return null;
}

function OptionsGroup({ children }: PropsWithChildren) {
  return <div className="divide-y rounded-md border">{children}</div>;
}

function SwitchOption({
  label,
  descriptions,
  descriptionOverride,
  checked,
  disabled,
  onCheckedChange,
}: {
  label: string;
  descriptions: {
    checked: string;
    unchecked: string;
  };
  descriptionOverride?: string;
  checked: boolean;
  disabled?: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const id = useId();
  const descriptionId = `${id}-description`;
  const description =
    descriptionOverride ??
    (checked ? descriptions.checked : descriptions.unchecked);
  const possibleDescriptions = [
    descriptions.checked,
    descriptions.unchecked,
    ...(descriptionOverride ? [descriptionOverride] : []),
  ];
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 px-3 py-2">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium leading-5">
          {label}
        </label>
        <OptionDescription
          id={descriptionId}
          description={description}
          possibleDescriptions={possibleDescriptions}
        />
      </div>
      <Switch
        id={id}
        size="sm"
        checked={checked}
        disabled={disabled}
        onCheckedChange={onCheckedChange}
        aria-label={label}
        aria-describedby={descriptionId}
      />
    </div>
  );
}

function RadioOption<Value extends string>({
  label,
  value,
  disabled,
  onValueChange,
  options,
}: {
  label: string;
  value: Value;
  disabled?: boolean;
  onValueChange: (value: Value) => void;
  options: readonly Choice<Value>[];
}) {
  const id = useId();
  const descriptionId = `${id}-description`;
  const selectedDescription = options.find(
    (option) => option.value === value,
  )?.description;
  return (
    <div className="flex min-h-14 flex-col items-stretch gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <div className="text-sm font-medium leading-5">{label}</div>
        <OptionDescription
          id={descriptionId}
          description={selectedDescription ?? ""}
          possibleDescriptions={options.map((option) => option.description)}
        />
      </div>
      <RadioGroup
        value={value}
        onValueChange={(nextValue) => onValueChange(nextValue as Value)}
        className="flex shrink-0 flex-wrap gap-x-5 gap-y-2 sm:justify-end"
        aria-label={label}
        aria-describedby={descriptionId}
        disabled={disabled}
      >
        {options.map((option, index) => {
          const optionId = `${id}-${index}`;
          return (
            <div key={option.value} className="flex items-center gap-2">
              <RadioGroupItem id={optionId} value={option.value} />
              <label htmlFor={optionId} className="text-sm">
                {option.label}
              </label>
            </div>
          );
        })}
      </RadioGroup>
    </div>
  );
}

function SelectOption<Value extends string>({
  label,
  value,
  disabled,
  onValueChange,
  options,
}: {
  label: string;
  value: Value;
  disabled?: boolean;
  onValueChange: (value: Value) => void;
  options: readonly Choice<Value>[];
}) {
  const id = useId();
  const descriptionId = `${id}-description`;
  const selectedDescription = options.find(
    (option) => option.value === value,
  )?.description;
  return (
    <div className="flex min-h-14 flex-col items-stretch gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <label htmlFor={id} className="text-sm font-medium leading-5">
          {label}
        </label>
        <OptionDescription
          id={descriptionId}
          description={selectedDescription ?? ""}
          possibleDescriptions={options.map((option) => option.description)}
        />
      </div>
      <Select
        value={value}
        disabled={disabled}
        onValueChange={(nextValue) => onValueChange(nextValue as Value)}
      >
        <SelectTrigger
          id={id}
          aria-describedby={descriptionId}
          className="h-8 w-full shrink-0 sm:w-44"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function OptionDescription({
  id,
  description,
  possibleDescriptions,
}: {
  id: string;
  description: string;
  possibleDescriptions: readonly string[];
}) {
  const sizingDescriptions = [...new Set(possibleDescriptions)].filter(
    (candidate) => candidate !== description,
  );
  return (
    <div className="mt-0.5 grid text-xs leading-4 text-muted-foreground">
      <p id={id} aria-live="polite" className="col-start-1 row-start-1">
        {description}
      </p>
      {sizingDescriptions.map((candidate) => (
        <p
          key={candidate}
          aria-hidden={true}
          className="invisible col-start-1 row-start-1"
        >
          {candidate}
        </p>
      ))}
    </div>
  );
}
