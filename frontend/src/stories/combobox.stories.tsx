/* Copyright 2023 Marimo. All rights reserved. */
import { Combobox, ComboboxItem } from "../components/ui/combobox";

export default {
  title: "Combobox",
  component: Combobox,
};

interface Framework {
  value: string;
  label: string;
}

const frameworks = [
  {
    value: "next.js",
    label: "Next.js",
  },
  {
    value: "sveltekit",
    label: "SvelteKit",
  },
  {
    value: "nuxt.js",
    label: "Nuxt.js",
  },
  {
    value: "remix",
    label: "Remix",
  },
  {
    value: "astro",
    label: "Astro",
  },
] satisfies Framework[];

export const Basic = () => (
  <div className="w-64 m-10">
    <Combobox
      placeholder="Select favorite framework"
      displayValue={(framework: Framework) => framework.label}
    >
      {frameworks.map((framework) => (
        <ComboboxItem key={framework.value} value={framework}>
          {framework.label}
        </ComboboxItem>
      ))}
    </Combobox>
  </div>
);

export const Multiple = () => (
  <div className="w-64 m-10">
    <Combobox
      placeholder="Select favorite frameworks"
      displayValue={(framework: Framework) => framework.label}
      multiple={true}
    >
      {frameworks.map((framework) => (
        <ComboboxItem key={framework.value} value={framework}>
          {framework.label}
        </ComboboxItem>
      ))}
    </Combobox>
  </div>
);

export const WithCustomFilterFn = () => (
  <div className="w-64 m-10">
    <Combobox
      placeholder="Select favorite frameworks"
      displayValue={(framework: Framework) => framework.label}
      filterFn={(value, search) =>
        value.charAt(0) === search.charAt(0) ? 1 : 0
      }
    >
      {frameworks.map((framework) => (
        <ComboboxItem key={framework.value} value={framework}>
          {framework.label}
        </ComboboxItem>
      ))}
    </Combobox>
  </div>
);
