# Copyright 2024 Marimo. All rights reserved.

import marimo

__generated_with = "0.11.0"
app = marimo.App()


@app.cell
def _(mo):
    mo.md(
        r"""
        # Bokeh: Network Graph Visualization

        Create interactive network graphs with hover information.
        Common usage: Relationship analysis, dependency graphs, social networks.
        """
    )
    return


@app.cell
def _():
    from bokeh.plotting import figure
    from bokeh.models import ColumnDataSource, NodesAndLinkedEdges
    from bokeh.layouts import column
    import networkx as nx
    import numpy as np

    # Create sample network
    G = nx.random_geometric_graph(20, 0.3, seed=42)

    # Get node positions
    pos = nx.spring_layout(G, seed=42)

    # Prepare node data
    node_x = [pos[node][0] for node in G.nodes()]
    node_y = [pos[node][1] for node in G.nodes()]
    node_size = [3 + 2*len(list(G.neighbors(node))) for node in G.nodes()]

    # Prepare edge data
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    # Create figure
    p = figure(
        width=500,
        height=500,
        title='Network Graph',
        tools='pan,wheel_zoom,box_zoom,reset,hover',
        active_scroll='wheel_zoom'
    )

    # Add edges
    p.line(edge_x, edge_y, line_color='gray', line_alpha=0.5)

    # Add nodes
    node_source = ColumnDataSource({
        'x': node_x,
        'y': node_y,
        'size': node_size,
        'connections': [len(list(G.neighbors(node))) for node in G.nodes()]
    })

    p.scatter('x', 'y',
             size='size',
             source=node_source,
             fill_color='navy',
             fill_alpha=0.6,
             hover_fill_color='red',
             line_color='white')

    # Add hover tooltips
    p.hover.tooltips = [
        ('Node ID', '$index'),
        ('Connections', '@connections')
    ]

    # Style
    p.grid.visible = False
    p.axis.visible = False

    p
    return (
        ColumnDataSource,
        G,
        NodesAndLinkedEdges,
        column,
        edge,
        edge_x,
        edge_y,
        figure,
        node_size,
        node_source,
        node_x,
        node_y,
        np,
        nx,
        p,
        pos,
        x0,
        x1,
        y0,
        y1,
    )


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
