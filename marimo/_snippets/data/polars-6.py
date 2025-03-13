# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Polars: String Operations and Pattern Matching

        This snippet demonstrates efficient string operations in Polars using pattern matching,
        transformations, and regular expressions. Shows string cleaning with `str.replace()`, 
        pattern extraction with `str.extract()`, and memory optimization using `Categorical` types.

        Example: `df.with_columns(pl.col("text").str.extract(r"pattern_(\d+)", 1))`
        """
    )
    return


@app.cell
def _():
    import polars as pl

    # Create sample text data with various patterns
    df = pl.DataFrame({
        'structured_text': ['User_' + str(i % 100) + '_Category_' + str(i % 3) for i in range(5)],
        'email': [f'user{i}@example.com' for i in range(5)],
        'mixed_text': [
            'user123@email.com',
            'JOHN DOE',
            'phone: 123-456-7890',
            'address: 123 Main St.',
            'support@company.com'
        ]
    })

    # Comprehensive string operations
    result = (
        df.lazy()
        .with_columns([
            # Basic transformations
            pl.col('mixed_text').str.to_lowercase().alias('lowercase_text'),
            pl.col('structured_text').str.replace_all('_', ' ').alias('cleaned_text'),

            # Pattern extraction
            pl.col('structured_text').str.extract(r'Category_(\d+)', 1).alias('category_num'),
            pl.col('email').str.split('@').list.get(0).alias('email_username'),

            # Pattern matching
            pl.col('mixed_text').str.contains(r'@').alias('is_email'),
            pl.col('mixed_text').str.contains(r'\d{3}-\d{3}-\d{4}').alias('is_phone'),

            # Advanced replacements
            pl.col('mixed_text').str.replace(
                r'\d{3}-\d{3}-\d{4}', 
                'XXX-XXX-XXXX'
            ).alias('masked_phone'),

            # Categorical optimization for repeated values
            pl.col('structured_text').cast(pl.Categorical).alias('categorical_text')
        ])
        .collect()
    )
    result
    return df, pl, result


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
