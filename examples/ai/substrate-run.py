import marimo

__generated_with = "0.7.18"
app = marimo.App(width="medium")


@app.cell
def __():
    import marimo as mo
    return mo,


@app.cell
def __(mo):
    API_KEY = mo.ui.text(
        label="Enter your [substrate.run](https://substrate.run) API Key:",
        kind="password",
    ).form(bordered=False)
    API_KEY
    return API_KEY,


@app.cell
def __(substrate):
    from substrate import GenerateImage, UpscaleImage, StableVideoDiffusion

    prompt = "aerial shot of rainforest at sunset clouds sun rays"
    image_node = GenerateImage(prompt=prompt)
    upscale_node = UpscaleImage(
        prompt=prompt,
        output_resolution=2048,
        image_uri=image_node.future.image_uri,
    )
    video_node = StableVideoDiffusion(
        image_uri=upscale_node.future.image_uri,
        store="hosted",
        motion_bucket_id=20,
        fps=10,
    )

    res = substrate.run(video_node)
    return (
        GenerateImage,
        StableVideoDiffusion,
        UpscaleImage,
        image_node,
        prompt,
        res,
        upscale_node,
        video_node,
    )


@app.cell
def __(mo, res, video_node):
    video = res.get(video_node)
    mo.image(video.video_uri)
    return video,


@app.cell
def __(API_KEY, mo):
    mo.stop(API_KEY.value is None)

    from substrate import Substrate, ComputeText, sb

    substrate = Substrate(api_key=API_KEY.value)
    return ComputeText, Substrate, sb, substrate


if __name__ == "__main__":
    app.run()
