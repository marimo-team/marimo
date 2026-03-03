# Run in the cloud with molab

[molab](https://molab.marimo.io/notebooks) is a free cloud-hosted marimo notebook
environment: run notebooks on cloud machines from your browser, zero setup required.
molab also integrates with GitHub, and supports embedding notebooks in other
webpages, making it easy to share your work.

!!! tip "Creating new notebooks"
    Go to [https://molab.new](https://molab.new) to instantly create a new notebook.

**Highlights**.

- ☁️ Use any Python package
- 🤖 Generate code with AI
- 📦 Install packages with a built-in package manager
- 🔗 Share links and open-in-molab badges
- 🌐 Embed interactive notebooks in your own webpages
- 📥 Download notebooks to your machine, reuse them as Python scripts or apps
- 📤 Upload local notebooks to the cloud from our CLI (coming soon)
- 🕹️ Real-time collaboration (coming soon)
- 🧩 Configure computational resources to obtain more CPU or GPU (coming soon)

## Sharing

!!! tip "Contribute to our community gallery"
    We welcome submissions to our [community gallery](https://marimo.io/gallery?tag=community).
    To propose an example, [reach out to us on Discord](https://marimo.io/discord).

molab notebooks are public but undiscoverable by default. For notebooks created
in molab, sharing is as easy as sending out the notebook's URL. Viewers will
see a static preview of your notebook and the option to fork it into their own
workspace.

### Preview notebooks from GitHub

molab makes it possible to to preview notebooks hosted on GitHub.

!!! tip "Example"
    See our [gallery
    repository](https://github.com/marimo-team/gallery-examples) for a canonical
    example of how to share previews of notebooks hosted on GitHub; every notebook
    in the [marimo gallery](https://marimo.io/gallery) is either an interactive
    or static preview of a notebook hosted on GitHub.


XXX

#### Interactive previews

XXX

#### Static previews


### Share open-in-molab badges

XXX

Share links to molab notebooks using our open in molab badge:

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL)

Use the following markdown snippet (replace the notebook URL with a link to your own notebook):

```
[![Open in molab](https://marimo.io/molab-shield.svg)](https://marimo.io/notebooks/nb_UJPnqcQzB7NuTtVNhwYBBp) 
```

## Embed in other webpages

### Embed notebooks from GitHub

/// tab | Code

```html
<iframe
    src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
    class="demo large"
    allowfullscreen
    loading="lazy"
>
</iframe>
```

///

/// tab | Live Example

<div class="demo-container">
    <iframe
        src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
        class="demo large"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

### Embed an empty notebook

/// tab | Code

```html
<iframe
    src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
    class="demo large"
    allowfullscreen
    loading="lazy"
>
</iframe>
```

///

/// tab | Live Example

<div class="demo-container">
    <iframe
        src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
        class="demo large"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

### Embed from source code

XXX

### Configuration


## Features

### Package management

Each notebook runs in an environment with several popular packages
pre-installed, including torch, numpy, polars, and more. marimo’s built-in
package manager will install additional packages as you import them (use the
package manage panel to install specific package versions).

### Storage

Notebooks get a limited amount persistent storage; view the file tree by
clicking the file icon in the sidebar. From here you can upload additional data
files.

### Run notebooks locally

You can download the notebook directory by clicking the download button, also
on the top-right. You can also just pass the notebook URL to marimo edit. For
example:

```bash
marimo edit https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL
```

Today, this brings just the notebook file down, and does not include your attached storage.

## FAQ

**What’s the difference between molab and Google Colab?** Google Colab is a hosted Jupyter notebook service provider. molab is a hosted [marimo notebook](https://github.com/marimo-team/marimo) service with similar compute and sharing capabilities, but powered by marimo notebooks instead of Jupyter. Unlike Colab, molab also supports embedding interactive notebooks in your own webpages,
no login required.

**Is molab free?** Yes.

**How do I get more RAM, CPU or GPUs?** [Reach out to us](https://marimo.io/discord) and we’ll see what we can do.

**How does molab relate to marimo’s open source notebook?** molab is a hosted
offering of marimo’s open source notebook with cloud-based compute and sharing
capabilities. You can use marimo open source on your own machine or on your own remote
servers.

**I’m a compute provider. How do I get plugged into molab as an offered backend?** [Get in touch](mailto:contact@marimo.io).

**How does molab relate to marimo’s WebAssembly playground?** The [WebAssembly playground](https://marimo.app) runs notebooks entirely in the browser through [Pyodide](https://pyodide.org/en/stable/). This makes for a snappy user experience, at the cost of limited compute and limited support for Python packages. The playground is well-suited for lightweight notebooks and embedding interactive notebooks in documentation, but it is not well-suited for modern ML or AI workflows. molab is currently entirely separate from the WebAssembly playground. In the future we may merge them into a unified experience.

**Why are you making molab?** See our [announcement blog post](https://marimo.io/blog/announcing-molab).
