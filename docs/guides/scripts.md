# Run as a script

You can run marimo notebooks as scripts at the command line, just like
any other Python script. For example,

```bash
python my_marimo_notebook.py
```

Running a notebook as a script is useful when your notebook has side-effects,
like writing to disk. Print statements and other console outputs will show
up in your terminal.

You can pass arguments to your notebook at the command-line: see
the [docs page on CLI args](/api/cli_args.md) to learn more.



:::{admonition} Producing notebook outputs
:class: note

To run as a script while also producing HTML of the notebook outputs, use

```bash
marimo export html notebook.py -o notebook.html
```
:::
