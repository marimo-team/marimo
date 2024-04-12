/* Copyright 2024 Marimo. All rights reserved. */
import { NativeSelect } from "@/components/ui/native-select";

export default {
  title: "NativeSelect",
  component: NativeSelect,
};

export const ShortOptions = {
  render: () => (
    <NativeSelect>
      <option>--</option>
      <option>a</option>
      <option>b</option>
      <option>c</option>
      <option>d</option>
    </NativeSelect>
  ),

  name: "Short Options",
};

export const OneLongOption = {
  render: () => (
    <NativeSelect>
      <option>--</option>
      <option>a</option>
      <option>b</option>
      <option>c</option>
      <option>defgh</option>
    </NativeSelect>
  ),

  name: "One long option",
};

export const OneReallyLongOption = {
  render: () => (
    <NativeSelect>
      <option>--</option>
      <option>a</option>
      <option>b</option>
      <option>c</option>
      <option>a really long option this is a really long option</option>
    </NativeSelect>
  ),

  name: "One really long option",
};
