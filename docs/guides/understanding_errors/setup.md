# Setup References

You're probably on this page because you just saw an error like this one:

<div align="center">
<figure>
<img src="/_static/docs_setup_error.png" width="700px"/>
</figure>
</div>

marimo raises this error when the setup cell references variables defined in
other cells. When using the setup cell, you can only use builtin functions.
In the case above, `image` is defined else where in the notebook, and hence
cannot be referenced.

## Why can't I refer to variables?

In it's goal to be reproducible, the behavior of marimo notebooks in script and
notebook mode needs to be consistent. Since script mode will always execute the
setup cell first, the notebook mode needs to do the same; and at notebook
start, no variables are defined.

## How do I fix this error?

Define all needed variables in the setup cell. For example, if you need to

```python
image = "image.png"
image
```

Alternatively, use another script or notebook, to contain more complex logic
that you can then just import.


```python
from myimages import image
image
```
