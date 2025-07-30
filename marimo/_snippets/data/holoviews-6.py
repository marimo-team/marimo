# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md(
        r"""
        # HoloViews: Statistical Analysis with Faceting

        Create comparative statistical visualizations.
        Common usage: A/B testing, multi-group analysis.
        Commonly used in: Research analysis, experiment evaluation.
        """
    )
    return


@app.cell
def __():
    import holoviews as hv
    import numpy as np
    import pandas as pd
    
    hv.extension('bokeh')
    
    # Generate experimental data
    np.random.seed(42)
    n_samples = 200
    
    # Simulate A/B test results across different segments
    segments = ['Segment A', 'Segment B', 'Segment C']
    variants = ['Control', 'Treatment']
    
    data = []
    for segment in segments:
        # Control group
        control_mean = np.random.uniform(20, 30)
        control_data = np.random.normal(control_mean, 5, n_samples)
        
        # Treatment group (with effect)
        effect = np.random.uniform(2, 5)
        treatment_data = np.random.normal(control_mean + effect, 5, n_samples)
        
        data.extend([
            {'segment': segment, 'variant': 'Control', 'value': v}
            for v in control_data
        ])
        data.extend([
            {'segment': segment, 'variant': 'Treatment', 'value': v}
            for v in treatment_data
        ])
    
    df = pd.DataFrame(data)
    
    # Create violin plots by segment
    violin = hv.Violin(df, ['segment', 'variant'], 'value').options(
        alpha=0.6,
        violin_fill_color='variant',
        cmap=['#1f77b4', '#ff7f0e']
    )
    
    # Add box plots overlay
    box = hv.BoxWhisker(df, ['segment', 'variant'], 'value').options(
        box_fill_alpha=0.4,
        box_color='white',
        whisker_color='black'
    )
    
    # Combine and style
    plot = (violin * box).options(
        width=800,
        height=400,
        title='Treatment Effect by Segment',
        tools=['hover'],
        xlabel='Segment',
        ylabel='Value',
        legend_position='top_right',
        show_grid=True
    )
    
    plot
    return box, df, hv, n_samples, np, pd, plot, segments, variants, violin


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run() 