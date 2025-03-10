/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { initializeUIElement } from "../core/dom/ui-element";
import { registerReactComponent } from "./core/registerReactComponent";
import { ButtonPlugin } from "./impl/ButtonPlugin";
import { CheckboxPlugin } from "./impl/CheckboxPlugin";
import { DatePickerPlugin } from "./impl/DatePickerPlugin";
import { DictPlugin } from "./impl/DictPlugin";
import { DropdownPlugin } from "./impl/DropdownPlugin";
import { FileUploadPlugin } from "./impl/FileUploadPlugin";
import { FileBrowserPlugin } from "./impl/FileBrowserPlugin";
import { FormPlugin } from "./impl/FormPlugin";
import { MultiselectPlugin } from "./impl/MultiselectPlugin";
import { NumberPlugin } from "./impl/NumberPlugin";
import { RadioPlugin } from "./impl/RadioPlugin";
import { RangeSliderPlugin } from "./impl/RangeSliderPlugin";
import { SliderPlugin } from "./impl/SliderPlugin";
import { SwitchPlugin } from "./impl/SwitchPlugin";
import { TextInputPlugin } from "./impl/TextInputPlugin";
import { TextAreaPlugin } from "./impl/TextAreaPlugin";
import type { IPlugin } from "./types";
import { DataTablePlugin } from "./impl/DataTablePlugin";
import type { IStatelessPlugin } from "./stateless-plugin";
import { AccordionPlugin } from "./layout/AccordionPlugin";
import { CalloutPlugin } from "./layout/CalloutPlugin";
import { JsonOutputPlugin } from "./layout/JsonOutputPlugin";
import { TabsPlugin } from "./impl/TabsPlugin";
import { CarouselPlugin } from "./layout/carousel/CarouselPlugin";
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
import { AnyWidgetPlugin } from "./impl/anywidget/AnyWidgetPlugin";
import { LazyPlugin } from "./layout/LazyPlugin";
import { NavigationMenuPlugin } from "@/plugins/layout/NavigationMenuPlugin";
import { initializeSidebarElement } from "./core/sidebar-element";
import { RoutesPlugin } from "./layout/RoutesPlugin";
import { DateTimePickerPlugin } from "./impl/DateTimePickerPlugin";
import { DateRangePickerPlugin } from "./impl/DateRangePlugin";
import { MimeRendererPlugin } from "./layout/MimeRenderPlugin";
import { ChatPlugin } from "./impl/chat/ChatPlugin";
import { DataEditorPlugin } from "./impl/DataEditorPlugin";
import { PanelPlugin } from "./impl/panel/PanelPlugin";
import { initPackagesPanelEventListener } from "@/core/event-listeners/packages-panel";

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

  // Initialize event listeners
  initPackagesPanelEventListener();

  // Initialize all the plugins.
  UI_PLUGINS.forEach(registerReactComponent);
  LAYOUT_PLUGINS.forEach(registerReactComponent);
}
