/* Copyright 2024 Marimo. All rights reserved. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { JsonOutput } from "../JsonOutput";

describe("JsonOutput with mimetype handling", () => {
  it("should render nested JSON with application/json: mimetype", () => {
    const data = {
      jsonData: 'application/json:{"nested":true}',
    };

    render(<JsonOutput data={data} format="auto" />);

    expect(screen.getByText("jsonData")).toBeInTheDocument();
    expect(screen.getByText("nested")).toBeInTheDocument();
  });

  it("should render common mimetypes (text/plain, text/html, image, video)", () => {
    const data = {
      text: "text/plain:Hello",
      html: "text/html:<strong>Bold</strong>",
      img: "image/png:data:image/png;base64,xyz...",
      vid: "video/mp4:data:video/mp4;base64,abc...",
    };

    const { container } = render(<JsonOutput data={data} format="auto" />);

    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("Bold")).toBeInTheDocument();
    expect(container.querySelector("img")).toBeInTheDocument();
    expect(container.querySelector("video")).toBeInTheDocument();
  });

  it("should render Python-specific types", () => {
    const data = {
      set: "text/plain+set:[1,2,3]",
      tuple: "text/plain+tuple:[10,20]",
    };

    render(<JsonOutput data={data} format="auto" />);

    expect(screen.getByText(/set\{1,2,3\}/)).toBeInTheDocument();
    expect(screen.getByText("(10,20)")).toBeInTheDocument();
  });

  it("should use fallback for unrecognized application/ mimetypes", () => {
    const data = {
      unknown: "application/unknown-type:data-content",
    };

    render(<JsonOutput data={data} format="auto" />);

    expect(
      screen.getByText(/application\/unknown-type:data-content/),
    ).toBeInTheDocument();
  });

  it("should handle mixed data types without crashing", () => {
    const data = {
      text: "text/plain:Simple",
      json: 'application/json:{"nested":true}',
      number: 42,
      boolean: true,
      null: null,
    };

    const { container } = render(<JsonOutput data={data} format="auto" />);

    expect(container).toBeInTheDocument();
    expect(screen.getByText("Simple")).toBeInTheDocument();
    expect(screen.getByText("nested")).toBeInTheDocument();
  });
});
