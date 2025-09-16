# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "accelerate==1.1.0",
#     "diffusers==0.31.0",
#     "marimo",
#     "numpy==2.1.3",
#     "torch==2.5.1",
#     "tqdm==4.66.6",
#     "transformers==4.46.1",
# ]
# ///

import marimo

__generated_with = "0.15.5"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import numpy as np
    import random
    import transformers

    import tqdm

    # Patch tqdm to work marimo notebooks
    tqdm.auto.tqdm = tqdm.notebook.tqdm

    from diffusers import DiffusionPipeline
    import torch

    MAX_SEED = np.iinfo(np.int32).max
    MAX_IMAGE_SIZE = 1024

    model_repo_id = (
        "stabilityai/sdxl-turbo"  # Replace to the model you would like to use
    )
    return (
        DiffusionPipeline,
        MAX_IMAGE_SIZE,
        MAX_SEED,
        mo,
        model_repo_id,
        random,
        torch,
    )


@app.cell
def _(mo, model_repo_id):
    mo.md(f"""# HuggingFace Text-to-Image: **{model_repo_id}**""")
    return


@app.cell(hide_code=True)
def _():
    examples = [
        "Astronaut in a jungle, cold color palette, muted colors, detailed, 8k",
        "An astronaut riding a green horse",
        "A delicious ceviche cheesecake slice",
    ]
    return (examples,)


@app.cell
def _(DiffusionPipeline, MAX_SEED, mo, model_repo_id, random, torch):
    device = "cuda" if torch.cuda.is_available() else "cpu"

    if torch.cuda.is_available():
        torch_dtype = torch.float16
    else:
        torch_dtype = torch.float32

    pipe = DiffusionPipeline.from_pretrained(
        model_repo_id, torch_dtype=torch_dtype
    )
    pipe = pipe.to(device)


    def infer(
        prompt,
        negative_prompt,
        seed,
        randomize_seed,
        width,
        height,
        guidance_scale,
        num_inference_steps,
    ):
        if randomize_seed:
            seed = random.randint(0, MAX_SEED)

        generator = torch.Generator().manual_seed(seed)

        image = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            width=width,
            height=height,
            generator=generator,
        ).images[0]

        return image, seed


    mo.output.clear()  # Clear loading tdqm
    return (infer,)


@app.cell
def _(mo):
    get_prompt, set_prompt = mo.state("")
    return get_prompt, set_prompt


@app.cell
def _(get_prompt, mo, set_prompt):
    prompt = mo.ui.text_area(
        placeholder="Enter your prompt",
        label="Prompt",
        full_width=True,
        value=get_prompt(),
        on_change=set_prompt,
    )
    return (prompt,)


@app.cell
def _(examples, mo, set_prompt):
    def _on_click(example):
        def handle(v):
            set_prompt(example)

        return handle


    buttons = mo.ui.array(
        [
            mo.ui.button(label=example, on_click=_on_click(example))
            for example in examples
        ]
    )

    example_options = mo.vstack(buttons)
    return (example_options,)


@app.cell
def _(MAX_IMAGE_SIZE, MAX_SEED, example_options, mo, prompt):
    run_button = mo.ui.run_button(label="Run", kind="success", full_width=True)

    negative_prompt = mo.ui.text_area(
        placeholder="Enter a negative prompt", label="Negative prompt"
    )

    seed = mo.ui.slider(start=0, stop=MAX_SEED, value=0, label="Seed")

    randomize_seed = mo.ui.checkbox(label="Randomize seed", value=True)

    width = mo.ui.slider(
        start=256, stop=MAX_IMAGE_SIZE, step=32, value=1024, label="Width"
    )
    height = mo.ui.slider(
        start=256, stop=MAX_IMAGE_SIZE, step=32, value=1024, label="Height"
    )

    guidance_scale = mo.ui.slider(
        start=0.0, stop=10.0, step=0.1, value=0.0, label="Guidance scale"
    )

    num_inference_steps = mo.ui.slider(
        start=1, stop=50, step=1, value=2, label="Number of inference steps"
    )

    # Create advanced settings in an accordion
    advanced_settings = mo.accordion(
        {
            "::lucide:list:: Examples": example_options,
            "::lucide:settings:: Advanced Settings": mo.hstack(
                [
                    mo.vstack([negative_prompt, seed, randomize_seed]),
                    mo.vstack(
                        [width, height, guidance_scale, num_inference_steps],
                        align="end",
                    ),
                ]
            ).style(padding="10px"),
        },
    )

    # Layout the main interface
    mo.vstack([prompt, run_button, advanced_settings])
    return (
        guidance_scale,
        height,
        negative_prompt,
        num_inference_steps,
        randomize_seed,
        run_button,
        seed,
        width,
    )


@app.cell
def _(mo):
    get_image, set_image = mo.state(None)
    return get_image, set_image


@app.cell
def _(
    guidance_scale,
    height,
    infer,
    mo,
    negative_prompt,
    num_inference_steps,
    prompt,
    randomize_seed,
    run_button,
    seed,
    set_image,
    width,
):
    mo.stop(not run_button.value)

    _image, _seed = infer(
        prompt.value,
        negative_prompt.value,
        seed.value,
        randomize_seed.value,
        width.value,
        height.value,
        guidance_scale.value,
        num_inference_steps.value,
    )
    set_image(_image)
    mo.output.clear()  # Clear loading tdqm
    return


@app.cell
def _(get_image):
    get_image()
    return


if __name__ == "__main__":
    app.run()
