/* Copyright 2026 Marimo. All rights reserved. */

export interface CellRecipe {
  id:
    | "interactive-control"
    | "form"
    | "read-csv-duckdb"
    | "reactive-altair-plot";
  title: string;
  description: string;
  keywords: string[];
  category: "build" | "data";
  requiredImports: Array<"marimo" | "altair">;
  cells: string[];
}

export const CELL_RECIPES: CellRecipe[] = [
  {
    id: "interactive-control",
    title: "Add an interactive control",
    description: "Create a slider that reactively updates an output",
    keywords: ["input", "slider", "ui", "widget"],
    category: "build",
    requiredImports: ["marimo"],
    cells: [
      `slider = mo.ui.slider(1, 100, value=50, label="Value")
slider`,
      `mo.md(f"Current value: **{slider.value}**")`,
    ],
  },
  {
    id: "form",
    title: "Build a form",
    description: "Collect several values with a single submit action",
    keywords: ["input", "submit", "batch", "ui"],
    category: "build",
    requiredImports: ["marimo"],
    cells: [
      `user_form = (
    mo.md(
        """
        **Name**

        {name}

        **Email**

        {email}
        """
    )
    .batch(
        name=mo.ui.text(placeholder="Your name"),
        email=mo.ui.text(placeholder="you@example.com"),
    )
    .form(submit_button_label="Submit")
)
user_form`,
      `user_form.value`,
    ],
  },
  {
    id: "read-csv-duckdb",
    title: "Read a CSV with DuckDB",
    description: "Load a local file or URL and query it with SQL",
    keywords: ["data", "file", "load", "query", "sql"],
    category: "data",
    requiredImports: ["marimo"],
    cells: [
      `csv_path = mo.ui.text(
    value="https://raw.githubusercontent.com/vega/vega-datasets/main/data/cars.csv",
    label="CSV path or URL",
    full_width=True,
)
csv_path`,
      `csv_data = mo.sql(
    f"""
    SELECT *
    FROM read_csv_auto('{csv_path.value}')
    """
)
csv_data`,
    ],
  },
  {
    id: "reactive-altair-plot",
    title: "Create a reactive Altair plot",
    description: "Drive a selectable chart with a marimo control",
    keywords: ["chart", "interactive", "plot", "slider", "visualization"],
    category: "build",
    requiredImports: ["marimo", "altair"],
    cells: [
      `power = mo.ui.slider(1, 4, value=2, label="Power")
power`,
      `_chart_data = [
    {"x": x, "y": x ** power.value}
    for x in range(1, 21)
]

chart = mo.ui.altair_chart(
    alt.Chart(alt.Data(values=_chart_data))
    .mark_line(point=True)
    .encode(
        x=alt.X("x:Q", title="x"),
        y=alt.Y("y:Q", title=f"x^{power.value}"),
        tooltip=["x:Q", "y:Q"],
    )
)
chart`,
      `chart.value`,
    ],
  },
];

export type CellRecipeId = CellRecipe["id"];

export function getCellRecipe(id: CellRecipeId): CellRecipe {
  const recipe = CELL_RECIPES.find((candidate) => candidate.id === id);
  if (!recipe) {
    throw new Error(`Unknown cell recipe: ${id}`);
  }
  return recipe;
}
