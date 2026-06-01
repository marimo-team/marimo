# Run in the cloud with molab

[molab](https://molab.marimo.io/notebooks) is a free cloud-hosted marimo notebook
environment. Notebooks run on powerful compute, with generous CPU,
RAM, and GPUs. molab is designed for sharing and is integrated with
GitHub; notebooks are public but undiscoverable by default.

!!! tip "Contribute to our community gallery!"
    We welcome submissions to our curated [community gallery](https://marimo.io/gallery?tag=community).
    To propose an example, share your notebook on socials and [tag us](publishing/public_gallery.md).


**Highlights**.

- ☁️ [Run on powerful compute](#compute), including NVIDIA GPUs
- 🤖 [Pair with coding agents](#work-with-ai) like Claude Code, or use built-in AI assistance
- 🪞 [Mirror notebooks from GitHub](#mirror-notebooks-from-github), with GitHub as the source of truth
- 🔗 Share [open-in-molab badges](#share-open-in-molab-badges)
- 🎞️ [Share as interactive slides or data apps](#share-as-slides-or-apps)
- 🌐 [Embed interactive notebooks](#embed-in-other-webpages) in your own webpages
- 📦 [Install packages](#package-management) with a built-in package manager
- 🛢️ Use a limited amount of [persistent storage](#storage) per notebook
- 📄 Export to PDF
- 📥 Run notebooks [on your machine](#run-notebooks-locally)

## Compute

molab notebooks run on cloud compute, giving you the full power of Python on a
traditional server. By default, each notebook runs with **4 CPUs and 32 GB of
RAM**.

**GPUs.** You can attach an NVIDIA RTX Pro 6000 Blackwell GPU — with 96 GB of
VRAM and 125 TFLOPS — to any notebook. Toggle the GPU by clicking the notebook
specs button in the app header. GPUs make it possible to finetune open-source
models, train and run modern ML workloads, and tackle compute-intensive
problems in the physical sciences, all from your browser.

<div align="center">
  <video autoplay muted loop playsinline width="700px" align="center">
    <source src="/_static/molab-attach-gpu.mp4" type="video/mp4">
  </video>
</div>

<p align="center"><em>Toggle GPUs by clicking the notebook specs button in the app header.</em></p>

**Long-running sessions.** Notebooks can run for as long as 12 hours before
molab shuts them down. Notebooks that are idle for more than 90 minutes are
automatically shut down.

**Fast startups.** molab notebooks are containers running marimo, preloaded
with popular packages for AI, ML, and computational science. They start up in
just a few seconds, so you can start coding right away.

## Work with AI

You can bring AI coding tools to bear on molab notebooks in two ways: control
notebooks with your favorite agent, or use built-in AI assistance (or both).

**Pair with coding agents.** Connect your favorite coding agent — such as Claude
Code, Codex, or OpenCode — to a running molab notebook using
[marimo pair](https://links.marimo.app/marimo-pair). Install the skill locally,
then copy the prompt that appears when you select "Pair with an agent" from the
notebook menu. marimo pair turns your notebook into a collaborative canvas you
share with your agent: it can do anything you can — write code, install
packages, manipulate UI widgets — and more.

**Built-in AI assistance.** The marimo editor has AI features integrated
throughout, including the ability to refactor existing cells and generate new
ones. In molab, these features are powered by free access to fast open-source
models, so you can generate code without bringing your own API key.

## Sharing

To share notebooks created in molab, just share the notebook's URL. Viewers
will see a static preview of your notebook and the option to fork it into their
own workspace.

### Mirror notebooks from GitHub

From the molab user interface, you can add notebooks hosted on GitHub. These
"synced" notebooks use GitHub as their source of truth: develop locally, push
your changes, and see them reflected in molab automatically. Synced notebooks
can be previewed statically or run on an ephemeral server.

To create a synced notebook, use the new notebook dropdown button on the molab homepage, and paste the URL of a notebook hosted on GitHub.

<div align="center">
  <img src="/_static/molab-sync-notebook.png" alt="Screenshot of the molab dialog for creating a synced notebook from a GitHub URL"/>
</div>

<p align="center"><em>Use GitHub as the source of truth for notebooks by
creating synced notebooks.</em></p>

This lets you add the notebook to your workspace. It also gives you sharing
links (and a snippet for an open-in-molab badge) so others can view the
notebook on molab, run it on an ephemeral server, or fork it into their own
workspace.

<div align="center">
  <img src="/_static/docs-create-a-synced-notebook.png" width="500px" alt="Screenshot of a synced molab notebook showing sharing links and an open-in-molab badge snippet"/>
</div>

<p align="center"><em>Add mirrored notebooks to your workspace or share them as links or badges.</em></p>

#### Static previews

> See our [gallery examples](https://github.com/marimo-team/gallery-examples) repository for best practices on previewing notebooks from GitHub.

By default, notebooks mirrored from GitHub show a static preview of the notebook. (The notebook dropdown in the app header allows you to toggle to interactive previews with a running notebook.)

In order for your static preview to include outputs, you must
commit the notebook's corresponding session JSON file, in the `__marimo__/session/`
directory that exists alongside the notebook. The session is automatically generated when
you run the notebook from the marimo editor; you can also generate the session
from the command-line with `marimo export session notebook.py`

### Share open-in-molab badges

Share links to molab notebooks using our open in molab badge:

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py)

Use the following markdown snippet (replace the notebook URL with a link to your own notebook):

```markdown
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py)
```

### Share as slides or apps

Every notebook can be shared as interactive slides or a data app:

- To share as a **data app**, choose "Run as app" from the share button on any
  running notebook.
- To share as **slides**, toggle the app preview of a notebook, then select
  "slides" from the view dropdown near the top of the page.

### Discover notebooks from the community

The molab landing page includes a **Discover** tab showcasing notebooks from
the community. Share your notebooks on socials and [tag us](publishing/public_gallery.md)
for a chance to be featured.

## Embed in other webpages

You can embed interactive molab notebooks in your own webpages using iframes.
Obtain iframe snippets by clicking the share button on interactive [molab previews
of GitHub notebooks](#mirror-notebooks-from-github), or construct
embeddable URLs yourself using the recipes below.

> Embedded notebooks run in the browser via WebAssembly, so your notebook must be
[WebAssembly-compatible](wasm.md). We also recommend creating these notebooks
[with `--sandbox`](package_management/inlining_dependencies.md) to make sure
their dependencies get installed.

### Embed notebooks from GitHub

Add `?embed=true` to an [interactive preview URL](#interactive-previews) to get an embeddable notebook:

/// tab | Code

```html
<iframe
    src="https://marimo.app/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms"
    allow="microphone"
    allowfullscreen
    loading="lazy"
>
</iframe>
```

///

/// tab | Live Example

<div class="demo-container">
    <iframe
        src="https://marimo.app/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms"
        allow="microphone"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

### Embed from source code

You can embed a notebook directly from its source code, without hosting it on
GitHub. Compress your notebook code using lz-string and pass it as a URL hash:

```
https://molab.marimo.io/new/wasm/?embed=true#code/{compressed}
```

/// tab | JavaScript

```javascript
import { compressToEncodedURIComponent } from "lz-string";

const url = `https://molab.marimo.io/new/wasm/?embed=true#code/${compressToEncodedURIComponent(code)}`;
```

///

/// tab | Python

```python
import lzstring

lz = lzstring.LZString()
compressed = lz.compressToEncodedURIComponent(code)
url = f"https://molab.marimo.io/new/wasm/?embed=true#code/{compressed}"
```

///

For example:

/// tab | Code

```html
<iframe
    src="https://marimo.app/?embed=true#code/MQAg9BIM4MYE4EsAOAXAUKOBTAjgVwWygFokBPFACwHsA7EAXhACIA+BgZgDoBGABmYYQAEyxIstUbRgIsURiADaQkKpYBbAIaJ11ZgBoVa5lpRIANtRTmEAIwNHVzWnnXkHoNS1jIyHkAC6QhBgaGgIbtRwKCBaOtRhAPqJAOYSWHCaKFjCiQDuCFQKzHxcAEylZYKaSEgKcRHUXACCtQAUaF4wUFCJAGYI5lgMzGB4UHBgljCa5mCJDbpgMOMo1Opc3VAOXpp4a4nC1Hm0lprCDIrMlCjq5swBhgCUYQVFNUhcUFgoeEgAXJ01BEkFEYotqCBNPJdEDVCCwSAXG4yFD5LQkHCQAjorEshYrDZbFxyASYtCQBZ0F4+nB1nizJZrHZNtRLHB5DiYgAZBC0LDaADKWBS6gk2WEAGE2VEtEh9CBeVAJdL2XKsbT6T5yFxJBFNGlsZFcTA6AA3NlmrAKlJ7HoITS0fqDbJwMJoAACH02WHM5jalAQokSptEDAAKnA8FgXqI+iBEm0noCvLouOphG1mNmsaBJb7zHhzNoQM19ussnRS9Ewl5w4H0VYsLZqNQANbQCJFrJyKEgGAF7twKHl0xV8Z8lJ9i2u2LUUTmBWO4Qgca9qhYLFEIsxNZ4ttYKG4t6UBlkolcEAASRieQpfKgSEIORAtlRikdR5iT6wA4CAZQMwoH+CAAA9WXUMBBUSaVaEyYQEDAZUsnGMAKjKDCMI4AAOMoeA4AA2AB2AiCIATj4AAWJ48VEV930FRp+RAWD4IQf8biAkCwHA01IOg1jzgQJ4uCxbNmBeLxsF+OBaHdL1ah9P0AyDLAQ3nYZI2jWMsHjRNkw1WV6iaAguD6WUOi8VMTIQLgEJgFAEDobQyDaABvLErOMb4cmYf45y4UyoBsUQ4DaZDogYPgFWVagkAYCpopAM1ZmjBhKLKGKaDyRIUsLTSoxjQwvK85xEmQ7Jtn8tMgpCjJwpQbQUHSmK1niioFTytKeEorLjly1KCu04qSq8ZgUkQXIoAQAAvLA-IC2rVLCiLmv4JLYvi9akq64ZKL4DbsnigBWDbsoG-KI0Kp4RtGpxlTEKrFts4LloapqGFO1q4oYbbOsG9KDtasRfrO-rdqu4bPJK5hbGmNtytm+bqpsr46pWxrIp4b74o4TLkoB7HoHOiGtKK6HVAAXwVYtbF9EYkG0TQxVdbYbop6A8FsdRCkSWx9jWJ1afp5gAFlNAPL8AEIdhKls4FCnIGAAMVmb4sUktRzLgdQtx+PBZJANptfUfQXjCBTPgHZTA2DUMhpjNA4wTY3ZQM6yvja12da4XbsXkAA5OhrQCjMs0lGwYA7AAqaPxclpqpdjkA91NdtVzqTRKSZCTNdUE8AvEDkEAe2gUBDTQYEoLAsyaiSUxK3KFBN33Bo5iagwUGcMgWDT-Vyq4O6mpGHgVAeyoquRR4TM0rgepBtkeGe56wXyl-HuHqCjxG5oePOQGkg36DaIezfk71rfMJ3dJd0-s6sVJJvdtQyUfoMT6fvWZLki2L4LFS7YaUho7Z2+kG6qDTGHOA4ksT1kPNgSQGRJyUiZizDI8g6aWDyFCPofRfy7mriASw6dlwgDwb6EA1B4wbnvigBUJ5qD7H7JQR0KRkE0OmuobsEoQBD1EmNbM+9D6yXPopS+AC1L22ATpPSSZwHQF0FYQMtApxMBqi9dG71IqHR+vwf6l0CI000JgkYgpFFUEnAYYm4MAZk33nDA2xlAoaLeqtKKXAdHxWwh4-RaVSiHRBqUY6RiTHMAAOJ2mmp+Bx0C+o5VJtdLEswkAsKcUtUKWjmr+Jxr9HxBNLqlAIsE6AR13F8GKcLcwpjzGnmSSwqxUASa2MSV4RmQxAKHjUajYQdIkBHBOJZEqcVHJ0CgJcZgAAhfKxBJTYGZsQAASr5BUzAABqhAgwlyscwcMBQbApBuNsgA8gOR0xAACiTVKDbIDlgOgo8OYQ0mdM2ZAp1CLOWRzSpIwAAKswfjZFlqofeaZKDISjm0RQUAamTgVDEpc5gUmaAVG0gFWAl55EyPFMmCoABWqwEB9DICMVaEkv5HyhIilhcLCxwBRf8jpMUYUqNEVbAs19ZF1ORa+Wl9L2nZCZa2CxKjn6qGdq-IeH8gyiqsokegTA+QoClcIdMmhQJJhogAahADwDmCFHzFjIG-FcTBoVCsoMa5VgqlGTlbvlMetB95eH1RYTQRqh4KBiZal1hrjU0oNna6MDrzajRgHKT1BBzC5DDTUNoqKOmBpDnKp1WsEApCXKBBQVIvhczJFAY2abppzQYG0PROq+A3TIZXX8Mo4AjDyIGQFKbVBqq4BERpxwrX9jlAwGN8psRlwyKCYsIzaAjH5NoOQKAyWjVbe27KbQfVur9d2mova5QKkVUOtkWQnJjucAKIg06EVIoYFyxNzaoTgW+OXNVJdEhUL6EmDmAwUg5tsHmxI5x8XKjaEMPoWSFSIAOWtBUbVfpwqsGsdQUVL3CPoK+2sah4NGwlZNM+v9FJ9DwNIUdHLkpNjgL3BcgzVBFqwP5RVCpaCUbLtR1w5UjrAQHXQg+Kjyqr2ELR1jm9t7ke4woXVNFiCsCRJ8SQ2hMhkHkeJS5Vd+wFn7HFWQ8gs6ZEkPSUWrZsDEH5GmygLYDYAHJ5CTy4DAqSKiFAYi4Opo4Gw4x7HMOXWSKQ2iuY4zkfehKeVbwRuRkAomeDyK8NC2Y5gFCubbYOtIHJSN3SSrQGKSMS0BcgLx-zSMQDaqJmlsAvm+NZZy5ey9HqmA2ewOILI8XRoVbEAKJVYW-Q0r8zvEOd6xkVpa4VuaGaS6-Q5k8RQ-xyMKhG0jAIrJyDPq8L6b4IW1BlbY2+rdsX82JeS8W8KSNNsxn3o0wlKB5BMGUKNNoxAiYXfZmdi7Cousc3O0THg12SptCSld26Vk3sKme59rwpaFQfYe0Te7Z2nsvdUEEGkURsQDoChVcYJI6QTTkL0Ww2gavIdYTXZEjHHqVqgFzRy1hhjMEYlwkdyC9jQcrPQLg9OrF8QsD8Pd5UieFCGCMAAIsHGWGsFtiufA5PdkWVHReyGt77IBsK7dSztzsc0niXv5DlJbfDTTTcvdrEQCpF10pEDAGifIQASFcBkHs4VAwAagDK0aWgoAdiYAhbAwuqwMCdxzLwKvjWKHt22AI1nPh0mUhVtk-o77EB6X1zrlbI8wGj79IbnuSp++T5D9uk1rNYFV5Nclhsh6srMjh13tAJHqTDHY-D-NBjRrlG0WgzMKMlP1zRljwnRNKhVLWuUMnswTMjSuLOneciqllDUEABdo60GjkpywBt5CanUCnQhVdqDfHoPG7I5mcytIZZVBQHlRrPOjDMuZ7ylnCAWqdu6ThgAcD4ARPguCgV3WYMAU6mgn99Bf0f4Aj-hBf4-4wzADYR8CrzP5-bAEwBf4QFp4sDAC4KIECCQGlQIHkKP5AGoG4K2BUTIFwFv64KP4YEoFWQEF9D7T7SYGkHACrzoR4GjSPAczMAnICi0AXJXJX74HAAVCgGwE3634HQwDYR9D0H8Fv4HQiEAFUFjTAD7S4Kf7SHGDACf6EGiE35kG4KnSKG364LQEVDaHwG4JER8D34GFkH7TEFcEiEVAKEkGMFH63L3L+TX7qEgG4F8FiHADQFyHf4kEyG4I+FmFoH7S2FWHkEP5qGv5oGgH6F+FKG6EHSRG-5YBf4HRBE+GUFxECFf7QFUH2FqCUxYg+YN5ihw6b5yAC6vjQidKKh8iHrCiijigj7d41BmR0jqCJA2C-olEhzlFQCKA9FLwBwJTHQERwb6yGzD5SgtFICQro7fBtAIDgB4jqr0DEA6o-ZK5kIw5LHG7qZpD15PABD7ygCqx+hVFRwpyQimDnh2CviRooDEDG6mhqg1BQBYjV7ObG5MBuRrIbL6oLTMBmj-FbIrK7KDD6bTr+TMAoB7KQnMCFFeDzE1HZppDlx9ptCfGOS0BcBon16N4rLAmTRbJK5570BTGj46yxqKDImLHLFaCrEgDrHg40Ta67H0D7E45HHmyejejYa4Z7r4ZmpKKWpDz+Q2YSZwBSZAZCTjDcbUaMY9jMaKrt5ia6jCCSZuq95iwaTEADDOYZD+SVbFgDgm6VyniXwT6FCng0K6DKhKbqC6D0CTxw5ZxtBlBwCarPbqoelek0QFAaZ5Db6CBeA+ZsTjCMBMB8CVEoYF5eAHiyQULlafDBz5rukgAz7hnyA5YKhlAZkHyynZk6qkldCMJlzHZqngptiY6qAuF3Smi0AWjmBWhtDKqRnQAiTQgoBkDiDGxnAoCVoJn8iLhzhhjMCYo1Azr8Ha6cgcnY716KmVSXpQ5qBCITH0A2baCihqptCmg4ZHYJ4VpcBdk9k1x8LCDdniA8mWxF4Cl0BV60qimTTiniYalSlurJbbn+R9D9kKmTzKllyqkSlvlSbakRLjBRJsExJmnyYulVyOjDnL4SAHxYDED4COiORzRXFIUiDrB8gYUlI9jBlFHxjTTbntnRkcyxm55Im0rYAmqVmNQQocx1mjS2gQUOhOj6mug1l3Rtnu4dnHnKinl9nUBZAE5ppaAMBkVaAKi6BjkTlIAhn8GXrQ7DizkFkqI46LlyDLkaxklqlbkMmYl0U5CHmdnCW9nnmXmOxhA+bJA9HJDtnMDJBaB8jJB+RJKKRRil4vBAA"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms"
    allow="microphone"
    allowfullscreen
    loading="lazy"
>
</iframe>
```

///

/// tab | Live Example

<div class="demo-container">
    <iframe
        src="https://marimo.app/?embed=true#code/MQAg9BIM4MYE4EsAOAXAUKOBTAjgVwWygFokBPFACwHsA7EAXhACIA+BgZgDoBGABmYYQAEyxIstUbRgIsURiADaQkKpYBbAIaJ11ZgBoVa5lpRIANtRTmEAIwNHVzWnnXkHoNS1jIyHkAC6QhBgaGgIbtRwKCBaOtRhAPqJAOYSWHCaKFjCiQDuCFQKzHxcAEylZYKaSEgKcRHUXACCtQAUaF4wUFCJAGYI5lgMzGB4UHBgljCa5mCJDbpgMOMo1Opc3VAOXpp4a4nC1Hm0lprCDIrMlCjq5swBhgCUYQVFNUhcUFgoeEgAXJ01BEkFEYotqCBNPJdEDVCCwSAXG4yFD5LQkHCQAjorEshYrDZbFxyASYtCQBZ0F4+nB1nizJZrHZNtRLHB5DiYgAZBC0LDaADKWBS6gk2WEAGE2VEtEh9CBeVAJdL2XKsbT6T5yFxJBFNGlsZFcTA6AA3NlmrAKlJ7HoITS0fqDbJwMJoAACH02WHM5jalAQokSptEDAAKnA8FgXqI+iBEm0noCvLouOphG1mNmsaBJb7zHhzNoQM19ussnRS9Ewl5w4H0VYsLZqNQANbQCJFrJyKEgGAF7twKHl0xV8Z8lJ9i2u2LUUTmBWO4Qgca9qhYLFEIsxNZ4ttYKG4t6UBlkolcEAASRieQpfKgSEIORAtlRikdR5iT6wA4CAZQMwoH+CAAA9WXUMBBUSaVaEyYQEDAZUsnGMAKjKDCMI4AAOMoeA4AA2AB2AiCIATj4AAWJ48VEV930FRp+RAWD4IQf8biAkCwHA01IOg1jzgQJ4uCxbNmBeLxsF+OBaHdL1ah9P0AyDLAQ3nYZI2jWMsHjRNkw1WV6iaAguD6WUOi8VMTIQLgEJgFAEDobQyDaABvLErOMb4cmYf45y4UyoBsUQ4DaZDogYPgFWVagkAYCpopAM1ZmjBhKLKGKaDyRIUsLTSoxjQwvK85xEmQ7Jtn8tMgpCjJwpQbQUHSmK1niioFTytKeEorLjly1KCu04qSq8ZgUkQXIoAQAAvLA-IC2rVLCiLmv4JLYvi9akq64ZKL4DbsnigBWDbsoG-KI0Kp4RtGpxlTEKrFts4LloapqGFO1q4oYbbOsG9KDtasRfrO-rdqu4bPJK5hbGmNtytm+bqpsr46pWxrIp4b74o4TLkoB7HoHOiGtKK6HVAAXwVYtbF9EYkG0TQxVdbYbop6A8FsdRCkSWx9jWJ1afp5gAFlNAPL8AEIdhKls4FCnIGAAMVmb4sUktRzLgdQtx+PBZJANptfUfQXjCBTPgHZTA2DUMhpjNA4wTY3ZQM6yvja12da4XbsXkAA5OhrQCjMs0lGwYA7AAqaPxclpqpdjkA91NdtVzqTRKSZCTNdUE8AvEDkEAe2gUBDTQYEoLAsyaiSUxK3KFBN33Bo5iagwUGcMgWDT-Vyq4O6mpGHgVAeyoquRR4TM0rgepBtkeGe56wXyl-HuHqCjxG5oePOQGkg36DaIezfk71rfMJ3dJd0-s6sVJJvdtQyUfoMT6fvWZLki2L4LFS7YaUho7Z2+kG6qDTGHOA4ksT1kPNgSQGRJyUiZizDI8g6aWDyFCPofRfy7mriASw6dlwgDwb6EA1B4wbnvigBUJ5qD7H7JQR0KRkE0OmuobsEoQBD1EmNbM+9D6yXPopS+AC1L22ATpPSSZwHQF0FYQMtApxMBqi9dG71IqHR+vwf6l0CI000JgkYgpFFUEnAYYm4MAZk33nDA2xlAoaLeqtKKXAdHxWwh4-RaVSiHRBqUY6RiTHMAAOJ2mmp+Bx0C+o5VJtdLEswkAsKcUtUKWjmr+Jxr9HxBNLqlAIsE6AR13F8GKcLcwpjzGnmSSwqxUASa2MSV4RmQxAKHjUajYQdIkBHBOJZEqcVHJ0CgJcZgAAhfKxBJTYGZsQAASr5BUzAABqhAgwlyscwcMBQbApBuNsgA8gOR0xAACiTVKDbIDlgOgo8OYQ0mdM2ZAp1CLOWRzSpIwAAKswfjZFlqofeaZKDISjm0RQUAamTgVDEpc5gUmaAVG0gFWAl55EyPFMmCoABWqwEB9DICMVaEkv5HyhIilhcLCxwBRf8jpMUYUqNEVbAs19ZF1ORa+Wl9L2nZCZa2CxKjn6qGdq-IeH8gyiqsokegTA+QoClcIdMmhQJJhogAahADwDmCFHzFjIG-FcTBoVCsoMa5VgqlGTlbvlMetB95eH1RYTQRqh4KBiZal1hrjU0oNna6MDrzajRgHKT1BBzC5DDTUNoqKOmBpDnKp1WsEApCXKBBQVIvhczJFAY2abppzQYG0PROq+A3TIZXX8Mo4AjDyIGQFKbVBqq4BERpxwrX9jlAwGN8psRlwyKCYsIzaAjH5NoOQKAyWjVbe27KbQfVur9d2mova5QKkVUOtkWQnJjucAKIg06EVIoYFyxNzaoTgW+OXNVJdEhUL6EmDmAwUg5tsHmxI5x8XKjaEMPoWSFSIAOWtBUbVfpwqsGsdQUVL3CPoK+2sah4NGwlZNM+v9FJ9DwNIUdHLkpNjgL3BcgzVBFqwP5RVCpaCUbLtR1w5UjrAQHXQg+Kjyqr2ELR1jm9t7ke4woXVNFiCsCRJ8SQ2hMhkHkeJS5Vd+wFn7HFWQ8gs6ZEkPSUWrZsDEH5GmygLYDYAHJ5CTy4DAqSKiFAYi4Opo4Gw4x7HMOXWSKQ2iuY4zkfehKeVbwRuRkAomeDyK8NC2Y5gFCubbYOtIHJSN3SSrQGKSMS0BcgLx-zSMQDaqJmlsAvm+NZZy5ey9HqmA2ewOILI8XRoVbEAKJVYW-Q0r8zvEOd6xkVpa4VuaGaS6-Q5k8RQ-xyMKhG0jAIrJyDPq8L6b4IW1BlbY2+rdsX82JeS8W8KSNNsxn3o0wlKB5BMGUKNNoxAiYXfZmdi7Cousc3O0THg12SptCSld26Vk3sKme59rwpaFQfYe0Te7Z2nsvdUEEGkURsQDoChVcYJI6QTTkL0Ww2gavIdYTXZEjHHqVqgFzRy1hhjMEYlwkdyC9jQcrPQLg9OrF8QsD8Pd5UieFCGCMAAIsHGWGsFtiufA5PdkWVHReyGt77IBsK7dSztzsc0niXv5DlJbfDTTTcvdrEQCpF10pEDAGifIQASFcBkHs4VAwAagDK0aWgoAdiYAhbAwuqwMCdxzLwKvjWKHt22AI1nPh0mUhVtk-o77EB6X1zrlbI8wGj79IbnuSp++T5D9uk1rNYFV5Nclhsh6srMjh13tAJHqTDHY-D-NBjRrlG0WgzMKMlP1zRljwnRNKhVLWuUMnswTMjSuLOneciqllDUEABdo60GjkpywBt5CanUCnQhVdqDfHoPG7I5mcytIZZVBQHlRrPOjDMuZ7ylnCAWqdu6ThgAcD4ARPguCgV3WYMAU6mgn99Bf0f4Aj-hBf4-4wzADYR8CrzP5-bAEwBf4QFp4sDAC4KIECCQGlQIHkKP5AGoG4K2BUTIFwFv64KP4YEoFWQEF9D7T7SYGkHACrzoR4GjSPAczMAnICi0AXJXJX74HAAVCgGwE3634HQwDYR9D0H8Fv4HQiEAFUFjTAD7S4Kf7SHGDACf6EGiE35kG4KnSKG364LQEVDaHwG4JER8D34GFkH7TEFcEiEVAKEkGMFH63L3L+TX7qEgG4F8FiHADQFyHf4kEyG4I+FmFoH7S2FWHkEP5qGv5oGgH6F+FKG6EHSRG-5YBf4HRBE+GUFxECFf7QFUH2FqCUxYg+YN5ihw6b5yAC6vjQidKKh8iHrCiijigj7d41BmR0jqCJA2C-olEhzlFQCKA9FLwBwJTHQERwb6yGzD5SgtFICQro7fBtAIDgB4jqr0DEA6o-ZK5kIw5LHG7qZpD15PABD7ygCqx+hVFRwpyQimDnh2CviRooDEDG6mhqg1BQBYjV7ObG5MBuRrIbL6oLTMBmj-FbIrK7KDD6bTr+TMAoB7KQnMCFFeDzE1HZppDlx9ptCfGOS0BcBon16N4rLAmTRbJK5570BTGj46yxqKDImLHLFaCrEgDrHg40Ta67H0D7E45HHmyejejYa4Z7r4ZmpKKWpDz+Q2YSZwBSZAZCTjDcbUaMY9jMaKrt5ia6jCCSZuq95iwaTEADDOYZD+SVbFgDgm6VyniXwT6FCng0K6DKhKbqC6D0CTxw5ZxtBlBwCarPbqoelek0QFAaZ5Db6CBeA+ZsTjCMBMB8CVEoYF5eAHiyQULlafDBz5rukgAz7hnyA5YKhlAZkHyynZk6qkldCMJlzHZqngptiY6qAuF3Smi0AWjmBWhtDKqRnQAiTQgoBkDiDGxnAoCVoJn8iLhzhhjMCYo1Azr8Ha6cgcnY716KmVSXpQ5qBCITH0A2baCihqptCmg4ZHYJ4VpcBdk9k1x8LCDdniA8mWxF4Cl0BV60qimTTiniYalSlurJbbn+R9D9kKmTzKllyqkSlvlSbakRLjBRJsExJmnyYulVyOjDnL4SAHxYDED4COiORzRXFIUiDrB8gYUlI9jBlFHxjTTbntnRkcyxm55Im0rYAmqVmNQQocx1mjS2gQUOhOj6mug1l3Rtnu4dnHnKinl9nUBZAE5ppaAMBkVaAKi6BjkTlIAhn8GXrQ7DizkFkqI46LlyDLkaxklqlbkMmYl0U5CHmdnCW9nnmXmOxhA+bJA9HJDtnMDJBaB8jJB+RJKKRRil4vBAA"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms"
        allow="microphone"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

Query parameters go before the hash:

```
https://marimo.app/?embed=true#code/{compressed}
```

For small notebooks (under 14 KB), you can also use the `code` query parameter
with URI encoding instead of lz-compression:

```
https://marimo.app/new/wasm/?embed=true&code={encodedURIComponent}
```


### Embed an empty editable notebook

Use this recipe to embed an empty editable notebook:

/// tab | Code

```html
<iframe
    src="https://marimo.app/?embed=true#code/JYWwDg9gTgLgBCAhlUEBQaD6mDmBTAOzykRjwBNMB3YGACzgF44AiAVwIGsCIqCW0iMGCYJkqAHQBBYQAoAlBjQABIWAkBjPABttacngBmcTAoBcaOFbhQ8MNlAJLgx7AUQg82JsxbYkwATYLBbWcGoSUBwKaEA"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms"
    allow="microphone"
    allowfullscreen
    loading="lazy"
>
</iframe>
```

///

/// tab | Live Example

<div class="demo-container">
    <iframe
        src="https://marimo.app/?embed=true#code/JYWwDg9gTgLgBCAhlUEBQaD6mDmBTAOzykRjwBNMB3YGACzgF44AiAVwIGsCIqCW0iMGCYJkqAHQBBYQAoAlBjQABIWAkBjPABttacngBmcTAoBcaOFbhQ8MNlAJLgx7AUQg82JsxbYkwATYLBbWcGoSUBwKaEA"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-forms"
        allow="microphone"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

### Query parameters

| Parameter | Default | Description |
| --- | --- | --- |
| `embed=true` | `false` | Hides the molab header for a cleaner embed |
| `mode=edit` | `read` | Allows viewers to edit code cells |
| `include-code=false` | `true` | Excludes code entirely (only works with `mode=read`) |
| `show-code=false` | `true` | Hides code by default, but viewers can still reveal it |


## Other features

### Package management

Each notebook runs in an environment with several popular packages
pre-installed, including torch, numpy, polars, and more. marimo’s built-in
package manager will install additional packages as you import them (use the
package manager sidebar panel to install specific package versions).

### Storage

Notebooks get a limited amount of persistent storage; view the file tree by
clicking the file icon in the sidebar. From here you can upload additional data
files.

### Run notebooks locally

You can download the notebook directory by clicking the download button, also
on the top-right. You can also just pass the notebook URL to marimo edit. For
example:

```bash
marimo edit https://molab.marimo.io/notebooks/nb_TWVGCgZZK4L8zj5ziUBNVL
```

Currently, this brings just the notebook file down, and does not include your attached storage.

## FAQ

**What’s the difference between molab and Google Colab?** Google Colab is a
hosted Jupyter notebook service provider. molab is a hosted [marimo
notebook](https://github.com/marimo-team/marimo) service with more compute
and sharing capabilities, and powered by marimo notebooks instead of Jupyter.
Unlike Colab, molab also supports embedding interactive notebooks in your own
webpages and sharing notebooks as apps and slides, no login required for readers.

**Is molab free?** Yes.

**What compute do I get?** By default, each notebook runs with 4 CPUs and 32 GB
of RAM. You can attach an NVIDIA RTX Pro 6000 Blackwell GPU (96 GB VRAM) to any
notebook using the notebook specs button in the app header. See
[Compute](#compute) for details.

**Can I use GPUs?** Yes. Attach a GPU to any notebook from the notebook specs
button in the app header. If you need additional compute beyond what's offered,
[reach out to us](https://marimo.io/discord).

**Does molab have built-in AI?** Yes. The marimo editor's AI features are
available in molab with free access to fast open-source models, and you can
also connect your own coding agent with [marimo pair](#work-with-ai).

**How does molab relate to marimo’s open source notebook?** molab is a hosted
offering of marimo’s open source notebook with cloud-based compute and sharing
capabilities. You can use marimo open source on your own machine or on your own remote
servers.

**How does molab relate to marimo’s WebAssembly playground?** The [WebAssembly playground](https://marimo.app) runs notebooks entirely in the browser through [Pyodide](https://pyodide.org/en/stable/). This makes for a snappy user experience, at the cost of limited compute and limited support for Python packages. The playground is well-suited for lightweight notebooks and embedding interactive notebooks in documentation, but it is not well-suited for modern ML or AI workflows. molab bridges the gap: develop notebooks with the full power of Python running on a traditional server, and (when compatible) share interactive previews using WebAssembly, which others can fork and develop further using a server-backed notebook.
