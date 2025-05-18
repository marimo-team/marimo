# Understanding errors

marimo imposes a few constraints on your notebook code:

* no multiply defined variables: each variable can be defined in only one cell
* no cycles: if one cell declares variable `a` and reads `b`, then another cannot declare `b` and read `a`.
* no `import *`: importing all symbols from a library is not allowed

!!! question "Why these constraints?"
    These constraints let marimo work its magic, making your notebooks:

    - **reproducible**, with a well-defined execution order, no hidden state, and no hidden bugs;
    - **executable** as a script;
    - **interactive** with UI elements that work without callbacks;
    - **shareable as a web app**, with far better performance that streamlit.

    As a bonus, you'll find that you end up with cleaner, reusable code.

When a cell violates any of these constraints, marimo doesn't run it and instead
reports an error. In these guides, we explain these errors and provide tips for
how to work around them.

These errors might be surprising at first, but spend just a
bit of time with marimo and adhering to these constraints will become second nature — and you'll get used to writing error-free code by default.

| Guide | Description |
|-------|-------------|
| [Multiple definitions](multiple_definitions.md) | How to deal with variables defined in multiple cells |
| [Import `*`](import_star.md) | Why you can't use `import *` |
| [Cycles](cycles.md) | How to resolve cycle errors |
| [setup](setup.md) | How to enable top level definitions |
