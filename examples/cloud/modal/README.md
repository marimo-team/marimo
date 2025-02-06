# Running marimo on Modal

This folder contains examples of how to use run marimo notebooks on Modal,
making it easy to get access to cloud GPUs. To get started, first create
a modal account and follow their onboarding.

## Editable notebooks
[modal_edit.py](modal_edit.py) has an example of how to spin up an editable
marimo notebook that runs on a Modal container. Run with

```bash
uvx -p 3.12 modal run modal_edit.py
```

You can configure your GPU selection by editing `modal_edit`.

## Run as apps

[modal_app.py](modal_app.py) has an example of how to deploy a read-only marimo
notebook as an app on Modal. Run with

```bash
uvx -p 3.12 modan run modal_run.py
```

