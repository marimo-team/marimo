# Publishing with MDX

[MDX](https://mdxjs.com/) combines Markdown with components for web frameworks.

marimo's [`mdx-marimo`](https://github.com/marimo-team/mdx-marimo) package
renders marimo code fences as connected, reactive cells inside MDX pages. Use
it to place Python, SQL, and Markdown cells among a site's prose and components.

Write a Python cell by adding `marimo` after the fence language:

````markdown
```python marimo
import marimo as mo

mo.md("hello")
```
````

Export an existing marimo notebook to MDX source:

```bash
marimo export md notebook.py -o notebook.mdx --flavor mdx
```

Add `remarkMarimo` to the host's MDX compiler, then load the package stylesheet
and browser runtime. For installation, framework setup, and supported cell
options, see the [mdx-marimo docs](https://marimo-team.github.io/mdx-marimo/).
