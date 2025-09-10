# Debugging marimo notebooks

## in marimo

### Using pdb in marimo notebooks

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


### Postmortem debugging

If your code raises an exception, you can use postmortem debugging to inspect the state of the program at the point where the exception occurred.
Click on the "Launch debugger" button as shown below:

![Postmortem debugging in marimo](./images/postmortem_debugging_in_marimo.png)


Other tools like code.interact() will also work in marimo notebooks.

!!! Danger
    Remember to continue or quit the debugger to avoid hanging the notebook!


## marimo as a script
Since marimo notebooks are standard Python files, you can run them as scripts
from the command line. The following command will run your marimo notebook and
drop you into the pdb debugger if an exception occurs, or if you hit a
breakpoint.

```bash
python -m pdb your_script.py
```

## Debugpy


## Debugpy
### When marimo launches an edit server

Coming soon: LSP support for marimo notebooks

## Tips for debugging marimo notebooks with AI

Debug With AI

@Errors
