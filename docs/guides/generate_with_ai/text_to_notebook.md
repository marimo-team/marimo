# Generate entire notebooks with AI

Use [`marimo new`](../../cli.md#marimo-new) at the command line to generate entirely new
notebooks using an LLM.

For example, type

```bash
marimo new "Plot an interactive 3D surface with matplotlib." 
```

to open a freshly generated notebook in your browser.

For long prompts, you can pass a text file instead:

```bash
marimo new my_prompt.txt
```

marimo's AI knows how to use marimo-specific UI elements and popular libraries
for working with data. To get inspired, visit <https://marimo.app/ai>. Some of
our favorites:

- [Dimensionality reduction](https://marimo.app/ai?q=Show+me+how+to+visualize+handwritten+digits+in+two+dimensions%2C+using+an+Altair+scatterplot.+Include+a+cell+that+shows+the+chart+value.+Make+the+chart+render+as+a+square.)
- [Smooth a time series](https://marimo.app/ai?q=Show+me+how+to+smooth+time+series+data+and+plot+it.+Use+a+well-known+stock+dataset+and+make+it+interactive)
- [Compute code complexity](https://marimo.app/ai?q=Build+a+tool+that+analyzes+Python+code+complexity+metrics+like+cyclomatic+complexity.+Let+me+input+code+snippets+and+see+visualizations+of+the+results.)
- [Visualize sorting algorithms](https://marimo.app/ai?q=Plot+an+interesting+3D+surface+with+matplotlib.+Include+an+interactive+element+to+control+the+shape+of+the+surface.)
