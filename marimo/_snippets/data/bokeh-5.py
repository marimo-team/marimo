# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bokeh: Statistical Visualization

        Create box plots and violin plots for statistical analysis.
        Common usage: Box plots for distribution comparison across categories.
        Commonly used in: research analysis, quality control, performance comparison.
        """
    )
    return


@app.cell
def __():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, FactorRange
    from bokeh.transform import factor_cmap
    import numpy as np
    import pandas as pd
    
    # Generate sample data for different groups
    np.random.seed(42)
    groups = ['Group A', 'Group B', 'Group C', 'Group D']
    data = []
    
    for group in groups:
        if group == 'Group A':
            values = np.random.normal(100, 15, 100)
        elif group == 'Group B':
            values = np.random.normal(85, 10, 100)
        elif group == 'Group C':
            values = np.random.normal(110, 20, 100)
        else:
            values = np.random.normal(95, 12, 100)
        
        # Calculate statistics
        q1 = np.percentile(values, 25)
        q2 = np.percentile(values, 50)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        upper = min(q3 + 1.5*iqr, np.max(values))
        lower = max(q1 - 1.5*iqr, np.min(values))
        
        # Store outliers
        outliers = values[(values < lower) | (values > upper)]
        
        data.append({
            'group': group,
            'lower': lower,
            'q1': q1,
            'q2': q2,
            'q3': q3,
            'upper': upper,
            'outliers': list(outliers)
        })
    
    df = pd.DataFrame(data)
    source = ColumnDataSource(df)
    
    # Create figure
    p = figure(
        height=400,
        width=600,
        title='Distribution Comparison Across Groups',
        x_range=groups,
        tools='pan,box_zoom,wheel_zoom,reset,save,hover'
    )
    
    # Add box glyphs
    p.vbar(x='group', top='q3', bottom='q1', width=0.7,
           fill_color=factor_cmap('group', 'Blues4', groups),
           line_color='black', source=source,
           legend_field='group')
    
    # Add whiskers
    p.segment(x0='group', y0='upper', x1='group', y1='q3',
              line_color='black', source=source)
    p.segment(x0='group', y0='lower', x1='group', y1='q1',
              line_color='black', source=source)
    
    # Add outlier points
    for i, group in enumerate(groups):
        outliers = df.iloc[i]['outliers']
        if len(outliers) > 0:
            p.circle([group]*len(outliers), outliers,
                    size=6, fill_alpha=0.6,
                    line_color='black', fill_color='red')
    
    # Style the plot
    p.xgrid.grid_line_color = None
    p.ygrid.grid_line_alpha = 0.1
    p.xaxis.axis_label = 'Groups'
    p.yaxis.axis_label = 'Values'
    
    # Configure hover tooltips
    p.hover.tooltips = [
        ('Group', '@group'),
        ('Median', '@q2{0.0}'),
        ('Q1', '@q1{0.0}'),
        ('Q3', '@q3{0.0}'),
        ('Upper', '@upper{0.0}'),
        ('Lower', '@lower{0.0}')
    ]
    
    # Configure legend
    p.legend.click_policy = 'hide'
    p.legend.location = 'top_right'
    
    p
    return (ColumnDataSource, FactorRange, data, df, factor_cmap, figure, group,
            groups, np, p, pd, source, values)


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
