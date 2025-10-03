# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "altair==5.4.1",
#     "duckdb==1.1.3",
#     "hdbscan==0.8.39",
#     "marimo",
#     "numba==0.60.0",
#     "numpy==2.0.2",
#     "polars==1.13.1",
#     "pyarrow==18.0.0",
#     "scikit-learn==1.5.2",
#     "umap-learn==0.5.7",
# ]
# ///

import marimo

__generated_with = "0.16.0"
app = marimo.App(width="medium")

with app.setup:
    # Use this notebook to follow along with the tutorial at
    # https://motherduck.com/blog/MotherDuck-Visualize-Embeddings-Marimo/
    import marimo as mo





if __name__ == "__main__":
    app.run()
