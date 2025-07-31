/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { NavigationMenuPlugin } from "@/plugins/layout/NavigationMenuPlugin";
import { initializeUIElement } from "../core/dom/ui-element";
import { registerReactComponent } from "./core/registerReactComponent";
import { initializeSidebarElement } from "./core/sidebar-element";
import { AnyWidgetPlugin } from "./impl/anywidget/AnyWidgetPlugin";
import { ButtonPlugin } from "./impl/ButtonPlugin";
import { CheckboxPlugin } from "./impl/CheckboxPlugin";
import { CodeEditorPlugin } from "./impl/CodeEditorPlugin";
import { ChatPlugin } from "./impl/chat/ChatPlugin";
import { DataEditorPlugin } from "./impl/DataEditorPlugin";
import { DataTablePlugin } from "./impl/DataTablePlugin";
import { DatePickerPlugin } from "./impl/DatePickerPlugin";
import { DateRangePickerPlugin } from "./impl/DateRangePlugin";
import { DateTimePickerPlugin } from "./impl/DateTimePickerPlugin";
import { DictPlugin } from "./impl/DictPlugin";
import { DropdownPlugin } from "./impl/DropdownPlugin";
import { DataExplorerPlugin } from "./impl/data-explorer/DataExplorerPlugin";
import { DataFramePlugin } from "./impl/data-frames/DataFramePlugin";
import { FileBrowserPlugin } from "./impl/FileBrowserPlugin";
import { FileUploadPlugin } from "./impl/FileUploadPlugin";
import { FormPlugin } from "./impl/FormPlugin";
import { MicrophonePlugin } from "./impl/MicrophonePlugin";
import { MultiselectPlugin } from "./impl/MultiselectPlugin";
import { NumberPlugin } from "./impl/NumberPlugin";
import { PanelPlugin } from "./impl/panel/PanelPlugin";
import { PlotlyPlugin } from "./impl/plotly/PlotlyPlugin";
import { RadioPlugin } from "./impl/RadioPlugin";
import { RangeSliderPlugin } from "./impl/RangeSliderPlugin";
import { RefreshPlugin } from "./impl/RefreshPlugin";
import { SliderPlugin } from "./impl/SliderPlugin";
import { SwitchPlugin } from "./impl/SwitchPlugin";
import { TabsPlugin } from "./impl/TabsPlugin";
import { TextAreaPlugin } from "./impl/TextAreaPlugin";
import { TextInputPlugin } from "./impl/TextInputPlugin";
import { VegaPlugin } from "./impl/vega/VegaPlugin";
import { AccordionPlugin } from "./layout/AccordionPlugin";
import { CalloutPlugin } from "./layout/CalloutPlugin";
import { CarouselPlugin } from "./layout/carousel/CarouselPlugin";
import { DownloadPlugin } from "./layout/DownloadPlugin";
import { ImageComparisonPlugin } from "./layout/ImageComparisonPlugin";
import { JsonOutputPlugin } from "./layout/JsonOutputPlugin";
import { LazyPlugin } from "./layout/LazyPlugin";
import { MimeRendererPlugin } from "./layout/MimeRenderPlugin";
import { MermaidPlugin } from "./layout/mermaid/MermaidPlugin";
import { ProgressPlugin } from "./layout/ProgressPlugin";
import { RoutesPlugin } from "./layout/RoutesPlugin";
import { StatPlugin } from "./layout/StatPlugin";
import { TexPlugin } from "./layout/TexPlugin";
import type { IStatelessPlugin } from "./stateless-plugin";
import type { IPlugin } from "./types";

// List of UI plugins
export const UI_PLUGINS: Array<IPlugin<any, unknown>> = [
  new ButtonPlugin(),
  new CheckboxPlugin(),
  DataTablePlugin,
  new DatePickerPlugin(),
  new DateTimePickerPlugin(),
  new DateRangePickerPlugin(),
  new DictPlugin(),
  new CodeEditorPlugin(),
  new DropdownPlugin(),
  new FileUploadPlugin(),
  FileBrowserPlugin,
  FormPlugin,
  new MicrophonePlugin(),
  new MultiselectPlugin(),
  new NumberPlugin(),
  new RadioPlugin(),
  new RefreshPlugin(),
  new RangeSliderPlugin(),
  new SliderPlugin(),
  new SwitchPlugin(),
  new TabsPlugin(),
  new TextAreaPlugin(),
  new TextInputPlugin(),
  new VegaPlugin(),
  new PlotlyPlugin(),
  ChatPlugin,
  DataExplorerPlugin,
  DataFramePlugin,
  LazyPlugin,
  DownloadPlugin,
  AnyWidgetPlugin,
  DataEditorPlugin,
  PanelPlugin,
];

// List of output / layout plugins
const LAYOUT_PLUGINS: Array<IStatelessPlugin<unknown>> = [
  new AccordionPlugin(),
  new CalloutPlugin(),
  new CarouselPlugin(),
  new ImageComparisonPlugin(),
  new JsonOutputPlugin(),
  new MimeRendererPlugin(),
  new MermaidPlugin(),
  new NavigationMenuPlugin(),
  new ProgressPlugin(),
  new RoutesPlugin(),
  new StatPlugin(),
  new TexPlugin(),
];

export function initializePlugins() {
  // Initialize custom DOM elements
  initializeUIElement();
  initializeSidebarElement();

  // Initialize all the plugins.
  UI_PLUGINS.forEach(registerReactComponent);
  LAYOUT_PLUGINS.forEach(registerReactComponent);
}
