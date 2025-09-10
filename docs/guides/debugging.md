# Debugging marimo Notebooks

## Debugging in marimo

### Using pdb in marimo Notebooks

marimo has direct support for pdb, the Python debugger. You can set breakpoints
in your code using the built-in `breakpoint()` function. When the code
execution reaches a breakpoint, it will pause, and you can inspect variables,
step through the code, and evaluate expressions.

Here's an example of how to use `breakpoint()` in a marimo notebook cell.

![PDB in marimo](./images/pdb_in_marimo.png)

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

!!! Note
    Since this block is runnable, you can test the debugger directly

```python
# Compute triangle numbers
triangle = 0
triangle_count = 20
for i in range(1, triangle_count):
    triangle += i # T_i = sum of 1..i
    # Debug at the 10th iteration
    # as a sanity check. Should be 55.
    if i == 10:
        breakpoint()
```

!!! Tip
    Click the little bug icon in the stack trace to add breakpoints.
    ![PDB breakpoint in marimo](./images/pdb_breakpoint_in_marimo.png)
    Clicking on the cell link will also take you to the cell where the error occurred.

### Postmortem Debugging

If your code raises an exception, you can use postmortem debugging to inspect the state of the program at the point where the exception occurred.
Click on the "Launch debugger" button as shown below:

![Postmortem debugging in marimo](./images/postmortem_debugging_in_marimo.png)


!!! Note
    Other tools like `code.interact()` will also work in marimo notebooks.

!!! Danger
    Remember to continue or quit the debugger to avoid hanging the notebook!

## Tips for debugging marimo notebooks with AI

TODO: Write this section, pull from https://github.com/marimo-team/marimo/pull/6158


## marimo as a Script
Since marimo notebooks are standard Python files, you can run them as scripts
from the command line. The following command will run your marimo notebook and
drop you into the pdb debugger if an exception occurs, or if you hit a
breakpoint.

```bash
python -m pdb your_script.py
```

## Debugpy

### Debugpy script mode
Likewise, using debugpy directly in marimo notebooks is supported.
If you want to use VSCode's debugging features, the following `launch.json`
will debug a marimo notebook in [script mode](link-to-script-mode).

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

### Debugpy edit mode
Partial support for edit mode debugging is also available.
This mode allows the marimo editor

![Postmortem debugging in marimo](./images/debugpy_edit_mode_in_marimo.png)

Note, this will disable marimo's internal debugging features.

!!! Danger
    This mode is blocking in VSCode, so you will need to interact with the
    debugger in your editor to regain control of the marimo notebook.

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

## Coming soon

LSP support for marimo notebooks is coming soon, and a native debug server
integration should be available in the near future.
