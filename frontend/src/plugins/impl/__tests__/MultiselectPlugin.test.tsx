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

    render(<MultiselectPlugin["prototype"]["render"] {...props} />);
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
      <MultiselectPlugin["prototype"]["render"] {...props} />,
    );
    expect(
      container.querySelector("[data-marimo-element='multiselect']"),
    ).not.toBeNull();
  });
});
