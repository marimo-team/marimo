# Debugging marimo notebooks

## Debugging in marimo

### Using pdb in marimo notebooks

marimo has direct support for pdb, the Python debugger. You can set breakpoints
in your code using the built-in `breakpoint()` function. When the code
execution reaches a breakpoint, it will pause, and you can inspect variables,
step through the code, and evaluate expressions.

Here's an example of how to use `breakpoint()` in a marimo notebook cell.

![PDB in marimo](/_static/docs-pdb-demo.png)

Type `help` in the debugger for a list of commands:

```txt
Documented commands (type help <topic>):
========================================
EOF    cl         disable     ignore    n        return  u          where
a      clear      display     interact  next     retval  unalias
alias  commands   down        j         p        run     undisplay
args   condition  enable      jump      pp       rv      unt
b      cont       exceptions  l         q        s       until
break  continue   exit        list      quit     source  up
bt     d          h           ll        r        step    w
c      debug      help        longlist  restart  tbreak  whatis

Miscellaneous help topics:
==========================
exec  pdb
```

!!! note
    Since this block is runnable, you can test the debugger directly

/// marimo-embed

```python
@app.cell
def _():
    # Compute triangle numbers
    triangle = 0
    triangle_count = 20
    for i in range(1, triangle_count):
        triangle += i # T_i = sum of 1..i
        # Debug at the 10th iteration
        # as a sanity check. Should be 55.
        if i == 10:
            breakpoint()
    return
```

///

!!! tip
    Click the little bug icon in the stack trace to add breakpoints.
    <video autoplay muted loop playsinline width="100%" align="center" src="/_static/docs-pdb-breakpoint.webm" alt="Animation showing how to click the bug icon to add PDB breakpoints">
    </video>
    Clicking on the cell link will also take you to the cell where the error occurred.

### Postmortem debugging

If your code raises an exception, you can use postmortem debugging to inspect
the state of the program at the point where the exception occurred. Click on
the "Launch debugger" button as shown below:

<video autoplay muted loop playsinline width="100%" align="center" src="/_static/docs-postmortem-debugging.webm" alt="Video demonstrating postmortem debugging with the Launch debugger button">
</video>


!!! note
    Other tools like the following will also work in marimo notebooks:

    ```python
      import code
      code.interact()
      return
    ```

!!! danger
    Remember to continue or quit the debugger to avoid hanging the notebook!

## Tips for debugging marimo notebooks with AI

marimo provides built-in integration with AI assistants to help debug your notebooks more effectively.

### Ask about notebook errors

When interacting with the AI chat, you can reference the notebook "Errors" with
the `@-symbol` to bring in comprehensive error information from your notebook,
making it easier to get targeted debugging help.

![Notebook Errors context in marimo](/_static/docs-notebook-errors-context.png)

### Best practices for AI-assisted debugging

**Provide context beyond just the error.** Include information about:
- What you were trying to accomplish
- Recent changes you made to the notebook
- Whether the error is new or recurring
- Related cells that might be involved

**Leverage marimo's debugging tools alongside AI.** Use marimo's [dataflow
tools](../guides/troubleshooting.md#verify-cell-connections) to understand cell
relationships, then share this information with AI assistants for more targeted
advice.

**Ask specific questions.** Instead of "Why is this broken?", try:
- "Why might this reactivity issue be occurring between these cells?"
- "How can I fix this import error in my marimo notebook?"
- "What's the best way to debug this performance issue in my data processing pipeline?"

!!! tip
    AI assistants are particularly helpful for explaining marimo-specific
    concepts like reactive execution, cell dependencies, and the differences
    between marimo notebooks and traditional Jupyter notebooks.

## Debugging notebooks as a script
Since marimo notebooks are standard Python files, you can run them as scripts
from the command line. The following command will run your marimo notebook and
drop you into the pdb debugger if an exception occurs, or if you hit a
breakpoint.

```bash
python -m pdb your_script.py
```

## External IDE debugging with `debugpy`

marimo supports debugging with IDEs, like VSCode, which natively support the
`debugpy` library. This allows you to set breakpoints, step through code, and
inspect variables directly from your IDE.

### Script mode
You can debug marimo notebooks in VSCode using the following `launch.json`.
This launch configuration will debug a marimo notebook in [script
mode](./scripts.md).

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "python",
      "request": "launch",
      "name": "marimo Debug: script mode",
      "program": "${file}",
      "debugOptions": [
          "--ignore", "*/site-packages/marimo/*"
      ]
    },
  ]
}
```

### Edit mode
Edit mode debugging allows the marimo editor to trigger breakpoints set in an
IDE like VSCode. Running in this mode will automatically start your notebook in
[watch mode](./editor_features/watching.md). Note that the file state and
editor must be consistent for break points to correctly work. If debugging is
not acting as expected, force a notebook save and toggle the relevant
breakpoints.

Use the following `launch.json` configuration to enable edit mode debugging:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
        "type": "debugpy",
        "request": "launch",
        "name": "marimo Debug: edit mode",
        "program": "${file}",
        "console": "integratedTerminal",
        "cwd": "${workspaceFolder}",
        "env": {
            "MARIMO_SCRIPT_EDIT": "1"
        },
        "justMyCode": false
    }
  ]
}
```

<video autoplay muted loop playsinline width="100%" align="center" src="/_static/docs-debugpy-edit-mode.webm" alt="Video showing debugpy edit mode debugging with VSCode hitting marimo breakpoints">
</video>

!!! note
    This will disable marimo's internal debugging features.

!!! danger
    This mode is blocking in VSCode, so you will need to interact with the
    debugger in your editor to regain control of the marimo notebook.


## Debug directly in VSCode

!!! note
    LSP support for marimo notebooks is coming soon, along with native debug server integration.
