# Run in the cloud with molab

!!! tip "Contribute to our community gallery!"
    We welcome submissions to our curated [community gallery](https://marimo.io/gallery?tag=community).
    To propose an example, [reach out to us on Discord](https://marimo.io/discord).

[molab](https://molab.marimo.io/notebooks) is a free cloud-hosted marimo notebook
environment: run notebooks on cloud machines from your browser, zero setup required.
molab also integrates with GitHub, and supports embedding notebooks in other
webpages, making it easy to share your work.

> Visit [https://molab.new](https://molab.new) to instantly create a new notebook.

molab notebooks are public but undiscoverable by default.

**Highlights**.

- ☁️ Use any Python package
- 🤖 Generate code with AI
- 📦 Install packages with a built-in package manager
- 🛢️ Use a limited amount of persistent storage per notebook
- 🔗 Share links and open-in-molab badges
- 🌐 Embed interactive notebooks in your own webpages
- 📥 Download notebooks to your machine, reuse them as Python scripts or apps
- 📤 Upload local notebooks to the cloud from our CLI (coming soon)
- 🕹️ Real-time collaboration (coming soon)
- 🧩 Configure computational resources to obtain more CPU or GPU (coming soon)

## Sharing

To share notebooks created in molab, just share the notebook's URL. Viewers
will see a static preview of your notebook and the option to fork it into their
own workspace.

### Preview notebooks from GitHub

> See our [gallery examples](https://github.com/marimo-team/gallery-examples) repository for best practices on previewing notebooks from GitHub.

In addition to sharing notebooks created in your workspace, you can also
preview notebooks hosted on GitHub. In some cases, these previews can be
interactive, but they are static by default.

#### Static previews


> Visit [molab.marimo.io/github](https://molab.marimo.io/github) to automatically generate preview URLs from GitHub links.

To construct a static (read-only, not interactive) preview, replace `github.com` in your notebook's GitHub URL
with `molab.marimo.io/github`. For example, a notebook at

```
https://github.com/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py
```

becomes

```
https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py
```

**Rendering outputs.** In order for your static preview to include outputs, you must
commit the notebooks corresponding session JSON file, in the `__marimo__/session/`
directory alongside the notebook. The session is automatically generated when
you run the notebook from the marimo editor; you can also regenerate the session
from the command-line with `marimo export session /path/to/notebook.py`

#### Interactive previews

Interactive previews let viewers run and interact with your notebook before
forking it. Append `/wasm` to the static preview URL to construct an
interactive preview. For example:

```
https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm
```

Your notebook must be [WebAssembly-compatible](wasm.md) for interactive
previews to work, and we also recommend creating these notebooks
[with `--sandbox`](package_management/inlining_dependencies.md)
to make sure their dependencies get installed. If you use coding
agents like Claude Code, you can use our [official
skills](generate_with_ai/skills.md) to automatically check for WebAssembly
compatibility of your notebooks.

### Share open-in-molab badges

Share links to molab notebooks using our open in molab badge:

[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py)

Use the following markdown snippet (replace the notebook URL with a link to your own notebook):

```markdown
[![Open in molab](https://marimo.io/molab-shield.svg)](https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py)
```

For notebooks hosted on GitHub, use our [badge
generator](https://molab.marimo.io/github) to automatically generate embeddable
links. If you want the preview to be interactive (and if your notebook is
[WebAssembly-compatible](wasm.md)), append `/wasm` to the URL.

## Embed in other webpages

You can embed interactive molab notebooks in your own webpages using iframes.
Embedded notebooks run in the browser via WebAssembly, so your notebook must
be [WebAssembly-compatible](wasm.md). We also recommend creating these
notebooks [with `--sandbox`](package_management/inlining_dependencies.md) to make sure their dependencies get installed.

### Embed notebooks from GitHub

Add `?embed=true` to an [interactive preview URL](#interactive-previews) to get an embeddable notebook:

/// tab | Code

```html
<iframe
    src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
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
        src="https://molab.marimo.io/github/marimo-team/gallery-examples/blob/main/notebooks/math/cellular-automaton-art.py/wasm?embed=true"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
        allow="microphone"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

### Embed from source code

You can embed a notebook directly from its source code, without hosting it on
GitHub. Compress your notebook code using
[lz-string](https://www.npmjs.com/package/lz-string) and pass it as a URL
hash:

```
https://molab.marimo.io/new/wasm/#code/{compressed}
```

For example, in JavaScript:

```javascript
import { compressToEncodedURIComponent } from "lz-string";

const url = `https://molab.marimo.io/new/wasm/#code/${compressToEncodedURIComponent(code)}`;
```

Query parameters go before the hash:

```
https://molab.marimo.io/new/wasm/?embed=true#code/{compressed}
```

For small notebooks (under 14 KB), you can also use the `code` query parameter
with URI encoding instead of lz-compression:

```
https://molab.marimo.io/new/wasm/?embed=true&code={encodedURIComponent}
```

/// tab | Code

```html
<iframe
    src="https://molab.marimo.io/new/wasm/?embed=true#code/MQAg9BIM4MYE4EsAOAXAUKOBTAjgVwWygFokBPFACwHsA7EAXhACIA+BgZgDoBGABmYYQAEyxIstUbRgIsURiADaQkKpYBbAIaJ11ZgBoVa5lpRIANtRTmEAIwNHVzWnnXkHoNS1jIyHkAC6QhBgaGgIbtRwKCBaOtRhAPqJAOYSWHCaKFjCiQDuCFQKzHxcAEylZYKaSEgKcRHUXACCtQAUaF4wUFCJAGYI5lgMzGB4UHBgljCa5mCJDbpgMOMo1Opc3VAOXpp4a4nC1Hm0lprCDIrMlCjq5swBhgCUYQVFNUhcUFgoeEgAXJ01BEkFEYotqCBNPJdEDVCCwSAXG4yFD5LQkHCQAjorEshYrDZbFxyASYtCQBZ0F4+nB1nizJZrHZNtRLHB5DiYgAZBC0LDaADKWBS6gk2WEAGE2VEtEh9CBeVAJdL2XKsbT6T5yFxJBFNGlsZFcTA6AA3NlmrAKlJ7HoITS0fqDbJwMJoAACH02WHM5jalAQokSptEDAAKnA8FgXqI+iBEm0noCvLouOphG1mNmsaBJb7zHhzNoQM19ussnRS9Ewl5w4H0VYsLZqNQANbQCJFrJyKEgGAF7twKHl0xV8Z8lJ9i2u2LUUTmBWO4Qgca9qhYLFEIsxNZ4ttYKG4t6UBlkolcEAASRieQpfKgSEIORAtlRikdR5iT6wA4CAZQMwoH+CAAA9WXUMBBUSaVaEyYQEDAZUsnGMAKjKDCMI4AAOMoeA4AA2AB2AiCIATj4AAWJ48VEV930FRp+RAWD4IQf8biAkCwHA01IOg1jzgQJ4uCxbNmBeLxsF+OBaHdL1ah9P0AyDLAQ3nYZI2jWMsHjRNkw1WV6iaAguD6WUOi8VMTIQLgEJgFAEDobQyDaABvLErOMb4cmYf45y4UyoBsUQ4DaZDogYPgFWVagkAYCpopAM1ZmjBhKLKGKaDyRIUsLTSoxjQwvK85xEmQ7Jtn8tMgpCjJwpQbQUHSmK1niioFTytKeEorLjly1KCu04qSq8ZgUkQXIoAQAAvLA-IC2rVLCiLmv4JLYvi9akq64ZKL4DbsnigBWDbsoG-KI0Kp4RtGpxlTEKrFts4LloapqGFO1q4oYbbOsG9KDtasRfrO-rdqu4bPJK5hbGmNtytm+bqpsr46pWxrIp4b74o4TLkoB7HoHOiGtKK6HVAAXwVYtbF9EYkG0TQxVdbYbop6A8FsdRCkSWx9jWJ1afp5gAFlNAPL8AEIdhKls4FCnIGAAMVmb4sUktRzLgdQtx+PBZJANptfUfQXjCBTPgHZTA2DUMhpjNA4wTY3ZQM6yvja12da4XbsXkAA5OhrQCjMs0lGwYA7AAqaPxclpqpdjkA91NdtVzqTRKSZCTNdUE8AvEDkEAe2gUBDTQYEoLAsyaiSUxK3KFBN33Bo5iagwUGcMgWDT-Vyq4O6mpGHgVAeyoquRR4TM0rgepBtkeGe56wXyl-HuHqCjxG5oePOQGkg36DaIezfk71rfMJ3dJd0-s6sVJJvdtQyUfoMT6fvWZLki2L4LFS7YaUho7Z2+kG6qDTGHOA4ksT1kPNgSQGRJyUiZizDI8g6aWDyFCPofRfy7mriASw6dlwgDwb6EA1B4wbnvigBUJ5qD7H7JQR0KRkE0OmuobsEoQBD1EmNbM+9D6yXPopS+AC1L22ATpPSSZwHQF0FYQMtApxMBqi9dG71IqHR+vwf6l0CI000JgkYgpFFUEnAYYm4MAZk33nDA2xlAoaLeqtKKXAdHxWwh4-RaVSiHRBqUY6RiTHMAAOJ2mmp+Bx0C+o5VJtdLEswkAsKcUtUKWjmr+Jxr9HxBNLqlAIsE6AR13F8GKcLcwpjzGnmSSwqxUASa2MSV4RmQxAKHjUajYQdIkBHBOJZEqcVHJ0CgJcZgAAhfKxBJTYGZsQAASr5BUzAABqhAgwlyscwcMBQbApBuNsgA8gOR0xAACiTVKDbIDlgOgo8OYQ0mdM2ZAp1CLOWRzSpIwAAKswfjZFlqofeaZKDISjm0RQUAamTgVDEpc5gUmaAVG0gFWAl55EyPFMmCoABWqwEB9DICMVaEkv5HyhIilhcLCxwBRf8jpMUYUqNEVbAs19ZF1ORa+Wl9L2nZCZa2CxKjn6qGdq-IeH8gyiqsokegTA+QoClcIdMmhQJJhogAahADwDmCFHzFjIG-FcTBoVCsoMa5VgqlGTlbvlMetB95eH1RYTQRqh4KBiZal1hrjU0oNna6MDrzajRgHKT1BBzC5DDTUNoqKOmBpDnKp1WsEApCXKBBQVIvhczJFAY2abppzQYG0PROq+A3TIZXX8Mo4AjDyIGQFKbVBqq4BERpxwrX9jlAwGN8psRlwyKCYsIzaAjH5NoOQKAyWjVbe27KbQfVur9d2mova5QKkVUOtkWQnJjucAKIg06EVIoYFyxNzaoTgW+OXNVJdEhUL6EmDmAwUg5tsHmxI5x8XKjaEMPoWSFSIAOWtBUbVfpwqsGsdQUVL3CPoK+2sah4NGwlZNM+v9FJ9DwNIUdHLkpNjgL3BcgzVBFqwP5RVCpaCUbLtR1w5UjrAQHXQg+Kjyqr2ELR1jm9t7ke4woXVNFiCsCRJ8SQ2hMhkHkeJS5Vd+wFn7HFWQ8gs6ZEkPSUWrZsDEH5GmygLYDYAHJ5CTy4DAqSKiFAYi4Opo4Gw4x7HMOXWSKQ2iuY4zkfehKeVbwRuRkAomeDyK8NC2Y5gFCubbYOtIHJSN3SSrQGKSMS0BcgLx-zSMQDaqJmlsAvm+NZZy5ey9HqmA2ewOILI8XRoVbEAKJVYW-Q0r8zvEOd6xkVpa4VuaGaS6-Q5k8RQ-xyMKhG0jAIrJyDPq8L6b4IW1BlbY2+rdsX82JeS8W8KSNNsxn3o0wlKB5BMGUKNNoxAiYXfZmdi7Cousc3O0THg12SptCSld26Vk3sKme59rwpaFQfYe0Te7Z2nsvdUEEGkURsQDoChVcYJI6QTTkL0Ww2gavIdYTXZEjHHqVqgFzRy1hhjMEYlwkdyC9jQcrPQLg9OrF8QsD8Pd5UieFCGCMAAIsHGWGsFtiufA5PdkWVHReyGt77IBsK7dSztzsc0niXv5DlJbfDTTTcvdrEQCpF10pEDAGifIQASFcBkHs4VAwAagDK0aWgoAdiYAhbAwuqwMCdxzLwKvjWKHt22AI1nPh0mUhVtk-o77EB6X1zrlbI8wGj79IbnuSp++T5D9uk1rNYFV5Nclhsh6srMjh13tAJHqTDHY-D-NBjRrlG0WgzMKMlP1zRljwnRNKhVLWuUMnswTMjSuLOneciqllDUEABdo60GjkpywBt5CanUCnQhVdqDfHoPG7I5mcytIZZVBQHlRrPOjDMuZ7ylnCAWqdu6ThgAcD4ARPguCgV3WYMAU6mgn99Bf0f4Aj-hBf4-4wzADYR8CrzP5-bAEwBf4QFp4sDAC4KIECCQGlQIHkKP5AGoG4K2BUTIFwFv64KP4YEoFWQEF9D7T7SYGkHACrzoR4GjSPAczMAnICi0AXJXJX74HAAVCgGwE3634HQwDYR9D0H8Fv4HQiEAFUFjTAD7S4Kf7SHGDACf6EGiE35kG4KnSKG364LQEVDaHwG4JER8D34GFkH7TEFcEiEVAKEkGMFH63L3L+TX7qEgG4F8FiHADQFyHf4kEyG4I+FmFoH7S2FWHkEP5qGv5oGgH6F+FKG6EHSRG-5YBf4HRBE+GUFxECFf7QFUH2FqCUxYg+YN5ihw6b5yAC6vjQidKKh8iHrCiijigj7d41BmR0jqCJA2C-olEhzlFQCKA9FLwBwJTHQERwb6yGzD5SgtFICQro7fBtAIDgB4jqr0DEA6o-ZK5kIw5LHG7qZpD15PABD7ygCqx+hVFRwpyQimDnh2CviRooDEDG6mhqg1BQBYjV7ObG5MBuRrIbL6oLTMBmj-FbIrK7KDD6bTr+TMAoB7KQnMCFFeDzE1HZppDlx9ptCfGOS0BcBon16N4rLAmTRbJK5570BTGj46yxqKDImLHLFaCrEgDrHg40Ta67H0D7E45HHmyejejYa4Z7r4ZmpKKWpDz+Q2YSZwBSZAZCTjDcbUaMY9jMaKrt5ia6jCCSZuq95iwaTEADDOYZD+SVbFgDgm6VyniXwT6FCng0K6DKhKbqC6D0CTxw5ZxtBlBwCarPbqoelek0QFAaZ5Db6CBeA+ZsTjCMBMB8CVEoYF5eAHiyQULlafDBz5rukgAz7hnyA5YKhlAZkHyynZk6qkldCMJlzHZqngptiY6qAuF3Smi0AWjmBWhtDKqRnQAiTQgoBkDiDGxnAoCVoJn8iLhzhhjMCYo1Azr8Ha6cgcnY716KmVSXpQ5qBCITH0A2baCihqptCmg4ZHYJ4VpcBdk9k1x8LCDdniA8mWxF4Cl0BV60qimTTiniYalSlurJbbn+R9D9kKmTzKllyqkSlvlSbakRLjBRJsExJmnyYulVyOjDnL4SAHxYDED4COiORzRXFIUiDrB8gYUlI9jBlFHxjTTbntnRkcyxm55Im0rYAmqVmNQQocx1mjS2gQUOhOj6mug1l3Rtnu4dnHnKinl9nUBZAE5ppaAMBkVaAKi6BjkTlIAhn8GXrQ7DizkFkqI46LlyDLkaxklqlbkMmYl0U5CHmdnCW9nnmXmOxhA+bJA9HJDtnMDJBaB8jJB+RJKKRRil4vBAA"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
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
        src="https://molab.marimo.io/new/wasm/?embed=true#code/MQAg9BIM4MYE4EsAOAXAUKOBTAjgVwWygFokBPFACwHsA7EAXhACIA+BgZgDoBGABmYYQAEyxIstUbRgIsURiADaQkKpYBbAIaJ11ZgBoVa5lpRIANtRTmEAIwNHVzWnnXkHoNS1jIyHkAC6QhBgaGgIbtRwKCBaOtRhAPqJAOYSWHCaKFjCiQDuCFQKzHxcAEylZYKaSEgKcRHUXACCtQAUaF4wUFCJAGYI5lgMzGB4UHBgljCa5mCJDbpgMOMo1Opc3VAOXpp4a4nC1Hm0lprCDIrMlCjq5swBhgCUYQVFNUhcUFgoeEgAXJ01BEkFEYotqCBNPJdEDVCCwSAXG4yFD5LQkHCQAjorEshYrDZbFxyASYtCQBZ0F4+nB1nizJZrHZNtRLHB5DiYgAZBC0LDaADKWBS6gk2WEAGE2VEtEh9CBeVAJdL2XKsbT6T5yFxJBFNGlsZFcTA6AA3NlmrAKlJ7HoITS0fqDbJwMJoAACH02WHM5jalAQokSptEDAAKnA8FgXqI+iBEm0noCvLouOphG1mNmsaBJb7zHhzNoQM19ussnRS9Ewl5w4H0VYsLZqNQANbQCJFrJyKEgGAF7twKHl0xV8Z8lJ9i2u2LUUTmBWO4Qgca9qhYLFEIsxNZ4ttYKG4t6UBlkolcEAASRieQpfKgSEIORAtlRikdR5iT6wA4CAZQMwoH+CAAA9WXUMBBUSaVaEyYQEDAZUsnGMAKjKDCMI4AAOMoeA4AA2AB2AiCIATj4AAWJ48VEV930FRp+RAWD4IQf8biAkCwHA01IOg1jzgQJ4uCxbNmBeLxsF+OBaHdL1ah9P0AyDLAQ3nYZI2jWMsHjRNkw1WV6iaAguD6WUOi8VMTIQLgEJgFAEDobQyDaABvLErOMb4cmYf45y4UyoBsUQ4DaZDogYPgFWVagkAYCpopAM1ZmjBhKLKGKaDyRIUsLTSoxjQwvK85xEmQ7Jtn8tMgpCjJwpQbQUHSmK1niioFTytKeEorLjly1KCu04qSq8ZgUkQXIoAQAAvLA-IC2rVLCiLmv4JLYvi9akq64ZKL4DbsnigBWDbsoG-KI0Kp4RtGpxlTEKrFts4LloapqGFO1q4oYbbOsG9KDtasRfrO-rdqu4bPJK5hbGmNtytm+bqpsr46pWxrIp4b74o4TLkoB7HoHOiGtKK6HVAAXwVYtbF9EYkG0TQxVdbYbop6A8FsdRCkSWx9jWJ1afp5gAFlNAPL8AEIdhKls4FCnIGAAMVmb4sUktRzLgdQtx+PBZJANptfUfQXjCBTPgHZTA2DUMhpjNA4wTY3ZQM6yvja12da4XbsXkAA5OhrQCjMs0lGwYA7AAqaPxclpqpdjkA91NdtVzqTRKSZCTNdUE8AvEDkEAe2gUBDTQYEoLAsyaiSUxK3KFBN33Bo5iagwUGcMgWDT-Vyq4O6mpGHgVAeyoquRR4TM0rgepBtkeGe56wXyl-HuHqCjxG5oePOQGkg36DaIezfk71rfMJ3dJd0-s6sVJJvdtQyUfoMT6fvWZLki2L4LFS7YaUho7Z2+kG6qDTGHOA4ksT1kPNgSQGRJyUiZizDI8g6aWDyFCPofRfy7mriASw6dlwgDwb6EA1B4wbnvigBUJ5qD7H7JQR0KRkE0OmuobsEoQBD1EmNbM+9D6yXPopS+AC1L22ATpPSSZwHQF0FYQMtApxMBqi9dG71IqHR+vwf6l0CI000JgkYgpFFUEnAYYm4MAZk33nDA2xlAoaLeqtKKXAdHxWwh4-RaVSiHRBqUY6RiTHMAAOJ2mmp+Bx0C+o5VJtdLEswkAsKcUtUKWjmr+Jxr9HxBNLqlAIsE6AR13F8GKcLcwpjzGnmSSwqxUASa2MSV4RmQxAKHjUajYQdIkBHBOJZEqcVHJ0CgJcZgAAhfKxBJTYGZsQAASr5BUzAABqhAgwlyscwcMBQbApBuNsgA8gOR0xAACiTVKDbIDlgOgo8OYQ0mdM2ZAp1CLOWRzSpIwAAKswfjZFlqofeaZKDISjm0RQUAamTgVDEpc5gUmaAVG0gFWAl55EyPFMmCoABWqwEB9DICMVaEkv5HyhIilhcLCxwBRf8jpMUYUqNEVbAs19ZF1ORa+Wl9L2nZCZa2CxKjn6qGdq-IeH8gyiqsokegTA+QoClcIdMmhQJJhogAahADwDmCFHzFjIG-FcTBoVCsoMa5VgqlGTlbvlMetB95eH1RYTQRqh4KBiZal1hrjU0oNna6MDrzajRgHKT1BBzC5DDTUNoqKOmBpDnKp1WsEApCXKBBQVIvhczJFAY2abppzQYG0PROq+A3TIZXX8Mo4AjDyIGQFKbVBqq4BERpxwrX9jlAwGN8psRlwyKCYsIzaAjH5NoOQKAyWjVbe27KbQfVur9d2mova5QKkVUOtkWQnJjucAKIg06EVIoYFyxNzaoTgW+OXNVJdEhUL6EmDmAwUg5tsHmxI5x8XKjaEMPoWSFSIAOWtBUbVfpwqsGsdQUVL3CPoK+2sah4NGwlZNM+v9FJ9DwNIUdHLkpNjgL3BcgzVBFqwP5RVCpaCUbLtR1w5UjrAQHXQg+Kjyqr2ELR1jm9t7ke4woXVNFiCsCRJ8SQ2hMhkHkeJS5Vd+wFn7HFWQ8gs6ZEkPSUWrZsDEH5GmygLYDYAHJ5CTy4DAqSKiFAYi4Opo4Gw4x7HMOXWSKQ2iuY4zkfehKeVbwRuRkAomeDyK8NC2Y5gFCubbYOtIHJSN3SSrQGKSMS0BcgLx-zSMQDaqJmlsAvm+NZZy5ey9HqmA2ewOILI8XRoVbEAKJVYW-Q0r8zvEOd6xkVpa4VuaGaS6-Q5k8RQ-xyMKhG0jAIrJyDPq8L6b4IW1BlbY2+rdsX82JeS8W8KSNNsxn3o0wlKB5BMGUKNNoxAiYXfZmdi7Cousc3O0THg12SptCSld26Vk3sKme59rwpaFQfYe0Te7Z2nsvdUEEGkURsQDoChVcYJI6QTTkL0Ww2gavIdYTXZEjHHqVqgFzRy1hhjMEYlwkdyC9jQcrPQLg9OrF8QsD8Pd5UieFCGCMAAIsHGWGsFtiufA5PdkWVHReyGt77IBsK7dSztzsc0niXv5DlJbfDTTTcvdrEQCpF10pEDAGifIQASFcBkHs4VAwAagDK0aWgoAdiYAhbAwuqwMCdxzLwKvjWKHt22AI1nPh0mUhVtk-o77EB6X1zrlbI8wGj79IbnuSp++T5D9uk1rNYFV5Nclhsh6srMjh13tAJHqTDHY-D-NBjRrlG0WgzMKMlP1zRljwnRNKhVLWuUMnswTMjSuLOneciqllDUEABdo60GjkpywBt5CanUCnQhVdqDfHoPG7I5mcytIZZVBQHlRrPOjDMuZ7ylnCAWqdu6ThgAcD4ARPguCgV3WYMAU6mgn99Bf0f4Aj-hBf4-4wzADYR8CrzP5-bAEwBf4QFp4sDAC4KIECCQGlQIHkKP5AGoG4K2BUTIFwFv64KP4YEoFWQEF9D7T7SYGkHACrzoR4GjSPAczMAnICi0AXJXJX74HAAVCgGwE3634HQwDYR9D0H8Fv4HQiEAFUFjTAD7S4Kf7SHGDACf6EGiE35kG4KnSKG364LQEVDaHwG4JER8D34GFkH7TEFcEiEVAKEkGMFH63L3L+TX7qEgG4F8FiHADQFyHf4kEyG4I+FmFoH7S2FWHkEP5qGv5oGgH6F+FKG6EHSRG-5YBf4HRBE+GUFxECFf7QFUH2FqCUxYg+YN5ihw6b5yAC6vjQidKKh8iHrCiijigj7d41BmR0jqCJA2C-olEhzlFQCKA9FLwBwJTHQERwb6yGzD5SgtFICQro7fBtAIDgB4jqr0DEA6o-ZK5kIw5LHG7qZpD15PABD7ygCqx+hVFRwpyQimDnh2CviRooDEDG6mhqg1BQBYjV7ObG5MBuRrIbL6oLTMBmj-FbIrK7KDD6bTr+TMAoB7KQnMCFFeDzE1HZppDlx9ptCfGOS0BcBon16N4rLAmTRbJK5570BTGj46yxqKDImLHLFaCrEgDrHg40Ta67H0D7E45HHmyejejYa4Z7r4ZmpKKWpDz+Q2YSZwBSZAZCTjDcbUaMY9jMaKrt5ia6jCCSZuq95iwaTEADDOYZD+SVbFgDgm6VyniXwT6FCng0K6DKhKbqC6D0CTxw5ZxtBlBwCarPbqoelek0QFAaZ5Db6CBeA+ZsTjCMBMB8CVEoYF5eAHiyQULlafDBz5rukgAz7hnyA5YKhlAZkHyynZk6qkldCMJlzHZqngptiY6qAuF3Smi0AWjmBWhtDKqRnQAiTQgoBkDiDGxnAoCVoJn8iLhzhhjMCYo1Azr8Ha6cgcnY716KmVSXpQ5qBCITH0A2baCihqptCmg4ZHYJ4VpcBdk9k1x8LCDdniA8mWxF4Cl0BV60qimTTiniYalSlurJbbn+R9D9kKmTzKllyqkSlvlSbakRLjBRJsExJmnyYulVyOjDnL4SAHxYDED4COiORzRXFIUiDrB8gYUlI9jBlFHxjTTbntnRkcyxm55Im0rYAmqVmNQQocx1mjS2gQUOhOj6mug1l3Rtnu4dnHnKinl9nUBZAE5ppaAMBkVaAKi6BjkTlIAhn8GXrQ7DizkFkqI46LlyDLkaxklqlbkMmYl0U5CHmdnCW9nnmXmOxhA+bJA9HJDtnMDJBaB8jJB+RJKKRRil4vBAA"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
        allow="microphone"
        allowfullscreen
        loading="lazy"
    >
    </iframe>
</div>

///

### Embed an empty editable notebook

Use this recipe to embed an empty editable notebook:

/// tab | Code

```html
<iframe
    src="https://molab.marimo.io/new/wasm/?embed=true&mode=edit#code/JYWwDg9gTgLgBCAhlUEBQaD6mDmBTAOzykRjwBNMB3YGACzgF44AiAVwIGsCIqCW0iMGCYJkqAHQBBYQAoAlBjQABIWAkBjPABttacngBmcTAoBcaOFbhQ8MNlAJLgx7AUQg82JsxbYkwATYLBbWcGoSUBwKaEA"
    sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
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
        src="https://molab.marimo.io/new/wasm/?embed=true&mode=edit#code/JYWwDg9gTgLgBCAhlUEBQaD6mDmBTAOzykRjwBNMB3YGACzgF44AiAVwIGsCIqCW0iMGCYJkqAHQBBYQAoAlBjQABIWAkBjPABttacngBmcTAoBcaOFbhQ8MNlAJLgx7AUQg82JsxbYkwATYLBbWcGoSUBwKaEA"
        class="demo large"
        sandbox="allow-scripts allow-same-origin allow-downloads allow-popups"
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


## Features

### Package management

Each notebook runs in an environment with several popular packages
pre-installed, including torch, numpy, polars, and more. marimo’s built-in
package manager will install additional packages as you import them (use the
package manager panel to install specific package versions).

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
notebook](https://github.com/marimo-team/marimo) service with similar compute
and sharing capabilities, but powered by marimo notebooks instead of Jupyter.
Unlike Colab, molab also supports embedding interactive notebooks in your own
webpages, no login required.

**Is molab free?** Yes.

**How do I get more RAM, CPU or GPUs?** [Reach out to us](https://marimo.io/discord) and we’ll see what we can do.

**How does molab relate to marimo’s open source notebook?** molab is a hosted
offering of marimo’s open source notebook with cloud-based compute and sharing
capabilities. You can use marimo open source on your own machine or on your own remote
servers.

**I’m a compute provider. How do I get plugged into molab as an offered backend?** [Get in touch](mailto:contact@marimo.io).

**How does molab relate to marimo’s WebAssembly playground?** The [WebAssembly playground](https://marimo.app) runs notebooks entirely in the browser through [Pyodide](https://pyodide.org/en/stable/). This makes for a snappy user experience, at the cost of limited compute and limited support for Python packages. The playground is well-suited for lightweight notebooks and embedding interactive notebooks in documentation, but it is not well-suited for modern ML or AI workflows. molab bridges the gap: develop notebooks with the full power of Python running on a traditional server, and (when compatible) share interactive previews using WebAssembly, which others can fork and develop further using a server-backed notebook.

**Why are you making molab?** See our [announcement blog post](https://marimo.io/blog/announcing-molab).
