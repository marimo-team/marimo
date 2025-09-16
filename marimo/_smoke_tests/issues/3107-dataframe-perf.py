import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell
def _():
    import polars as pl
    import numpy as np
    from typing import Tuple
    import marimo as mo


    def create_test_dataframe(num_rows: int) -> Tuple[pl.DataFrame, list[str]]:
        """
        Create a large test dataframe with various column types including 1200 float columns.

        Args:
            num_rows: Number of rows to generate

        Returns:
            Tuple of (DataFrame, list of group values)
        """
        # Set random seed for reproducibility
        np.random.seed(42)

        # Generate random data for different column types
        data = {
            "int_col1": np.random.randint(0, 1000000, num_rows),
            "int_col2": np.random.randint(-1000000, 1000000, num_rows),
            "float_col1": np.random.normal(0, 1, num_rows),
            "float_col2": np.random.uniform(0, 100, num_rows),
            "str_col1": np.random.choice(["A", "B", "C", "D", "E"], num_rows),
            "str_col2": [f"val_{i}" for i in np.random.randint(0, 1000, num_rows)],
            "bool_col1": np.random.choice([True, False], num_rows),
            "bool_col2": np.random.choice([True, False], num_rows),
            "group": np.random.choice(
                ["group1", "group2", "group3", "group4"], num_rows
            ),
        }

        # Add 1200 float columns with different distributions
        for i in range(1200):
            if i % 3 == 0:
                # Normal distribution
                data[f"float_normal_{i}"] = np.random.normal(0, 1, num_rows)
            elif i % 3 == 1:
                # Uniform distribution
                data[f"float_uniform_{i}"] = np.random.uniform(-100, 100, num_rows)
            else:
                # Exponential distribution
                data[f"float_exp_{i}"] = np.random.exponential(1, num_rows)

        # Create the original derived columns
        data.update(
            {
                f"derived_col_{i}": data["int_col1"]
                + np.random.randint(0, 100, num_rows)
                for i in range(10)
            }
        )

        df = pl.DataFrame(data)
        unique_groups = df["group"].unique().to_list()

        return df
    return create_test_dataframe, pl


@app.cell
def _(create_test_dataframe):
    num_rows = 10
    df = create_test_dataframe(num_rows)
    return (df,)


@app.cell
def _(df, pl):
    x = df.filter(pl.col("group") == "group2")
    return


if __name__ == "__main__":
    app.run()
