import { render, screen } from "@testing-library/react";
import { MultiselectPlugin } from "../MultiselectPlugin";
import { IPluginProps } from "../../types";
import { vi, describe, it, expect } from "vitest";

describe("MultiselectPlugin", () => {
  it("renders correctly", () => {
    const props: IPluginProps<string[], any> = {
      value: ["foo"],
      setValue: vi.fn(),
      data: {
        label: "Test",
        options: ["foo", "bar"],
        fullWidth: false,
      },
      host: {} as any,
      functions: {} as any,
    };

    render(<MultiselectPlugin.prototype.render {...props} />);
    expect(screen.getByText("Test")).toBeInTheDocument();
  });

  it("has data-marimo-element attribute", () => {
    const props: IPluginProps<string[], any> = {
      value: ["foo"],
      setValue: vi.fn(),
      data: {
        label: "Test",
        options: ["foo", "bar"],
        fullWidth: false,
      },
      host: {} as any,
      functions: {} as any,
    };

    const { container } = render(<MultiselectPlugin.prototype.render {...props} />);
    expect(container.querySelector("[data-marimo-element='multiselect']")).not.toBeNull();
  });
});
