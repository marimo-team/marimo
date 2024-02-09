/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { initializeUIElement } from "../core/dom/UIElement";
import { registerReactComponent } from "./core/registerReactComponent";
import { ButtonPlugin } from "./impl/ButtonPlugin";
import { CheckboxPlugin } from "./impl/CheckboxPlugin";
import { DatePickerPlugin } from "./impl/DatePickerPlugin";
import { DictPlugin } from "./impl/DictPlugin";
import { DropdownPlugin } from "./impl/DropdownPlugin";
import { FileUploadPlugin } from "./impl/FileUploadPlugin";
import { FormPlugin } from "./impl/FormPlugin";
import { MultiselectPlugin } from "./impl/MultiselectPlugin";
import { NumberPlugin } from "./impl/NumberPlugin";
import { RadioPlugin } from "./impl/RadioPlugin";
import { SliderPlugin } from "./impl/SliderPlugin";
import { SwitchPlugin } from "./impl/SwitchPlugin";
import { TextInputPlugin } from "./impl/TextInputPlugin";
import { TextAreaPlugin } from "./impl/TextAreaPlugin";
import { IPlugin } from "./types";
import { DataTablePlugin } from "./impl/DataTablePlugin";
import { IStatelessPlugin } from "./stateless-plugin";
import { AccordionPlugin } from "./layout/AccordionPlugin";
import { CalloutPlugin } from "./layout/CalloutPlugin";
import { JsonOutputPlugin } from "./layout/JsonOutputPlugin";
import { TabsPlugin } from "./impl/TabsPlugin";
import { TexPlugin } from "./layout/TexPlugin";
import { RefreshPlugin } from "./impl/RefreshPlugin";
import { MicrophonePlugin } from "./impl/MicrophonePlugin";
import { DownloadPlugin } from "./layout/DownloadPlugin";
import { ProgressPlugin } from "./layout/ProgressPlugin";
import { VegaPlugin } from "./impl/vega/VegaPlugin";
import { StatPlugin } from "./layout/StatPlugin";
import { DataFramePlugin } from "./impl/data-frames/DataFramePlugin";
import { PlotlyPlugin } from "./impl/plotly/PlotlyPlugin";
import { CodeEditorPlugin } from "./impl/CodeEditorPlugin";
import { DataExplorerPlugin } from "./impl/data-explorer/DataExplorerPlugin";
import { MermaidPlugin } from "./layout/mermaid/MermaidPlugin";

// List of UI plugins
export const UI_PLUGINS: Array<IPlugin<any, unknown>> = [
  new ButtonPlugin(),
  new CheckboxPlugin(),
  DataTablePlugin,
  new DatePickerPlugin(),
  new DictPlugin(),
  new CodeEditorPlugin(),
  new DropdownPlugin(),
  new FileUploadPlugin(),
  FormPlugin,
  new MicrophonePlugin(),
  new MultiselectPlugin(),
  new NumberPlugin(),
  new RadioPlugin(),
  new RefreshPlugin(),
  new SliderPlugin(),
  new SwitchPlugin(),
  new TabsPlugin(),
  new TextAreaPlugin(),
  new TextInputPlugin(),
  new VegaPlugin(),
  new PlotlyPlugin(),
  DataExplorerPlugin,
  DataFramePlugin,
];

// List of output / layout plugins
const LAYOUT_PLUGINS: Array<IStatelessPlugin<unknown>> = [
  new AccordionPlugin(),
  new CalloutPlugin(),
  new DownloadPlugin(),
  new JsonOutputPlugin(),
  new ProgressPlugin(),
  new StatPlugin(),
  new TabsPlugin(),
  new TexPlugin(),
  new MermaidPlugin(),
];

export function initializePlugins() {
  // Initialize UIElement
  initializeUIElement();

  // Initialize all the plugins.
  UI_PLUGINS.forEach(registerReactComponent);
  LAYOUT_PLUGINS.forEach(registerReactComponent);
}
