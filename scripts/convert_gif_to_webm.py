import marimo

__generated_with = "0.10.13"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""# Convert gifs to webm format""")
    return


@app.cell
def _(mo):
    mo.md(
        """
        You can either use the UI below or run:

        ```bash
        python convert_gif_to_webm.py -- --folder /path/to/folder
        ```
        """
    )
    return


@app.cell
def _():
    import os
    import subprocess
    from pathlib import Path

    return Path, os, subprocess


@app.cell(hide_code=True)
def _(Path, os, subprocess):
    def get_gifs_from_folder(input_folder):
        return list(Path(input_folder).glob("**/*.gif"))

    def convert_gif_to_webm(gif_files, force=False):
        if not gif_files:
            print("No GIF files found in the specified folder.")
            return

        print(f"Found {len(gif_files)} GIF files. Starting conversion...")

        for gif_path in gif_files:
            output_path = gif_path.with_suffix(".webm")

            def print_size_info(gif_path, output_path):
                original_size = os.path.getsize(gif_path)
                new_size = os.path.getsize(output_path)
                reduction = (1 - new_size / original_size) * 100
                print(f"Size reduced by {reduction:.1f}%")
                print(f"Original: {original_size/1024:.1f}KB")
                print(f"New: {new_size/1024:.1f}KB")
                print("-" * 50)

            if output_path.exists() and not force:
                print(f"Skipping {gif_path} - output already exists")
                print_size_info(gif_path, output_path)
                continue

            print(f"Converting: {gif_path}")

            try:
                # FFmpeg command to convert GIF to WebM
                cmd = [
                    "ffmpeg",
                    "-i",
                    str(gif_path),
                    "-c:v",
                    "libvpx-vp9",  # Use VP9 codec
                    "-b:v",
                    "1M",  # Bitrate
                    "-auto-alt-ref",
                    "0",
                    "-f",
                    "webm",
                    str(output_path),
                ]

                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=20
                )

                if result.returncode == 0:
                    print(f"Successfully converted: {output_path}")
                    print_size_info(gif_path, output_path)
                else:
                    print(f"Error converting {gif_path}")
                    print(f"Error: {result.stderr}")

            except subprocess.TimeoutExpired:
                print(
                    f"Timeout converting {gif_path} - took longer than 20 seconds"
                )
            except Exception as e:
                print(f"Error processing {gif_path}: {str(e)}")

    return convert_gif_to_webm, get_gifs_from_folder


@app.cell
def _(mo):
    files = mo.ui.file_browser(multiple=True)
    force = mo.ui.checkbox(label="Force overwrite existing files")
    return files, force


@app.cell
def _(Path, files):
    gifs = [Path(f.path) for f in files.value]
    return (gifs,)


@app.cell
def _(gifs, mo):
    run_selection = mo.ui.run_button(
        label="Convert selection", disabled=len(gifs) == 0
    )
    run_selection = mo.ui.run_button(
        label="Convert all in folder", disabled=len(gifs) == 0
    )
    run_selection
    return (run_selection,)


@app.cell
def _(convert_gif_to_webm, gifs, mo, run_selection, force):
    if run_selection.value:
        with mo.status.spinner("Converting GIFs to WebM..."):
            convert_gif_to_webm(gifs, force=force.value)
    return


@app.cell
def _(convert_gif_to_webm, get_gifs_from_folder, mo, os):
    folder_path = mo.cli_args().get("folder")
    _force = mo.cli_args().get("force")
    if _force is None:
        _force = False

    if mo.app_meta().mode != "script":
        mo.stop(True, "Not running as a script")

    if not os.path.exists(folder_path):
        raise Exception("Specified folder does not exist!")
    else:
        convert_gif_to_webm(get_gifs_from_folder(folder_path), force=_force)
    return folder_path


if __name__ == "__main__":
    app.run()
