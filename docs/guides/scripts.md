# Run as a script

You can run marimo notebooks as scripts at the command line, just like
any other Python script. For example,

```bash
python my_marimo_notebook.py
```


Running a notebook as a script is useful when your notebook has side-effects,
like writing to disk. Print statements and other console outputs will show
up in your terminal.

```{admonition} Future plans
:class: note

In the future, we may make UI element values configurable as command-line
arguments, and optionally generate a PDF or HTML of the cell outputs.
```

