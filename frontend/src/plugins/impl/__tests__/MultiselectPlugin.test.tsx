import { render, screen } from "@testing-library/react";
import { MultiselectPlugin } from "../MultiselectPlugin";
import type { IPluginProps } from "../../types";
import { vi, describe, it, expect } from "vitest";

// Define the data type for the multiselect plugin
interface MultiselectData {
  label: string;
  options: string[];
  fullWidth: boolean;
}

// Create a wrapper component to render the plugin
const MultiselectWrapper = (props: IPluginProps<string[], MultiselectData>) => {
  // Call the render method directly
  return MultiselectPlugin.prototype.render(props);
};

describe("MultiselectPlugin", () => {
  it("renders correctly", () => {
    const props: IPluginProps<string[], MultiselectData> = {
      value: ["foo"],
      setValue: vi.fn(),
      data: {
        label: "Test",
        options: ["foo", "bar"],
        fullWidth: false,
      },
      host: {} as HTMLElement,
      functions: {},
    };

    render(<MultiselectWrapper {...props} />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("has data-marimo-element attribute", () => {
    const props: IPluginProps<string[], MultiselectData> = {
      value: ["foo"],
      setValue: vi.fn(),
      data: {
        label: "Test",
        options: ["foo", "bar"],
        fullWidth: false,
      },
      host: {} as HTMLElement,
      functions: {},
    };

    const { container } = render(
      <MultiselectWrapper {...props} />
    );
    expect(
      container.querySelector("[data-marimo-element='multiselect']")
    ).not.toBeNull();
  });
});
