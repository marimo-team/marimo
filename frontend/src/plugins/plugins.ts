/* Copyright 2023 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { initializeUIElement } from "../core/dom/UIElement";
import { registerReactComponent } from "./core/componentFactory";
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
import { TabsPlugin } from "./layout/TabsPlugin";
import { TexPlugin } from "./layout/TexPlugin";

// List of UI plugins
const UI_PLUGINS: Array<IPlugin<any, unknown>> = [
  new ButtonPlugin(),
  new CheckboxPlugin(),
  new DatePickerPlugin(),
  new DictPlugin(),
  new DropdownPlugin(),
  new FileUploadPlugin(),
  new FormPlugin(),
  new MultiselectPlugin(),
  new NumberPlugin(),
  new RadioPlugin(),
  new DataTablePlugin(),
  new SliderPlugin(),
  new SwitchPlugin(),
  new TextInputPlugin(),
  new TextAreaPlugin(),
];

// List of output / layout plugins
const LAYOUT_PLUGINS: Array<IStatelessPlugin<unknown>> = [
  new AccordionPlugin(),
  new CalloutPlugin(),
  new JsonOutputPlugin(),
  new TabsPlugin(),
  new TexPlugin(),
];

export function initializePlugins() {
  // Initialize UIElement
  initializeUIElement();

  // Initialize all the plugins.
  UI_PLUGINS.forEach(registerReactComponent);
  LAYOUT_PLUGINS.forEach(registerReactComponent);
}
