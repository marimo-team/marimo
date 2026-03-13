# Share cloud notebooks with molab

[molab](https://molab.marimo.io/notebooks) is a cloud-hosted marimo notebook
workspace that lets you rapidly experiment on data using Python and SQL. We’re
giving molab (**mo** for marimo) to you, our community, for *free*.

To create your first notebook, visit:
[https://molab.marimo.io/notebooks](https://molab.marimo.io/notebooks).

!!! tip "Contribute example notebooks!"
    We welcome exciting companies and projects to contribute examples notebooks,
    which are featured on the homepage with an organization's name and logo. To propose an example,
    [reach out to us on GitHub](https://github.com/marimo-team/marimo/issues).

**Highlights**.

- ⚡️ Build powerful notebooks using [marimo](https://github.com/marimo-team/marimo), a next-gen open-source Python notebook built entirely from scratch that [solves](https://marimo.io/blog/lessons-learned) [long-standing](https://marimo.io/blog/python-not-json) [problems](https://leomurta.github.io/papers/pimentel2019a.pdf) with Jupyter
- ☁️ Use any Python package, thanks to our cloud backend
- 🤖 Generate code with AI
- 📦 Upload data files
- 🔗 Share links and badges (notebooks are public but undiscoverable, like secret GitHub Gists)
- 📥 Download notebooks to your machine, reuse them as Python scripts or apps
- 📤 Upload local notebooks to the cloud from our CLI (coming soon)
- 🕹️ Real-time collaboration (coming soon)
- 🧩 Configure computational resources to obtain more CPU or GPU (coming soon)


## Sharing

molab notebooks are public but undiscoverable by default.

### URL

You can share notebooks by URL. Here's an example:

> https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL

### Open in molab badge

Share links to molab notebooks using our open in molab badge:

[![Open in molab](https://marimo.io/molab-shield.png)](https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL)

Use the following markdown snippet (replace the notebook URL with a link to your own notebook):

```
[![Open in molab](https://marimo.io/molab-shield.png)](https://marimo.io/notebooks/nb_UJPnqcQzB7NuTtVNhwYBBp) 
```

## Packages

Each notebook runs in an environment with several popular packages
pre-installed, including torch, numpy, polars, and more. marimo’s built-in
package manager will install additional packages as you import them (use the
package manage panel to install specific package versions).

## Storage

Notebooks get persistent storage; view the file tree by clicking the file icon
in the sidebar. From here you can upload additional data files, which are
stored in a Cloudflare R2 bucket.

## Run notebook locally

You can download the notebook directory by clicking the download button, also
on the top-right. You can also just pass the notebook URL to marimo edit. For
example:

```bash
marimo edit https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL
```

Today, this brings just the notebook file down, and does not include your attached storage.

## FAQ

**What’s the difference between molab and Google Colab?** Google Colab is a hosted Jupyter notebook service provider. molab is a hosted [marimo notebook](https://github.com/marimo-team/marimo) service with similar compute and sharing capabilities, but powered by marimo notebooks instead of Jupyter.

**Is molab marimo’s enterprise product?** No. If you’re interested in a
next-generation data platform for modern AI and data workloads — with marimo’s
trademark developer experience, complete with security and governance required
for enterprises — [get in touch](mailto:contact@marimo.io).

**Is molab free?** molab is currently free to use, as long as usage is reasonable. Our goal is to make is as easy as possible for our community to use marimo notebooks.

**How do I get more RAM, CPU or GPUs?** [Reach out to us](https://marimo.io/discord) and we’ll see what we can do!

**I’m a compute provider.  How do I get plugged into molab as an offered backend?** [Get in touch](mailto:contact@marimo.io).

**How does molab relate to marimo’s open source notebook?** molab is a hosted version of marimo’s open source notebook. You can use marimo on your own machine or on your own remote servers.

**How does molab relate to marimo’s WebAssembly playground?** The [WebAssembly playground](https://marimo.app) runs notebooks entirely in the browser through [Pyodide](https://pyodide.org/en/stable/). This makes for a snappy user experience, at the cost of limited compute and limited support for Python packages. The playground is well-suited for lightweight notebooks and embedding interactive notebooks in documentation, but it is not well-suited for modern ML or AI workflows. molab is currently entirely separate from the WebAssembly playground. In the future we may merge them into a unified experience.

**How does molab relate to marimo’s community cloud?** Our [community cloud](https://marimo.io/dashboard) provides a place to organize and share WebAssembly notebooks. molab is currently entirely separate from the community cloud. In the future we may merge them into a unified experience.

**Why are you making molab?** See our [announcement blog post](https://marimo.io/blog/announcing-molab).
