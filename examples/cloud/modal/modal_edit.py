import secrets
import subprocess
import time

import modal

app = modal.App(
    image=modal.Image.debian_slim()
    .pip_install("marimo>=0.12.8", "modal>=0.73.166")
    .add_local_dir("nbs", remote_path="/root/nbs")
)

TOKEN = secrets.token_urlsafe(16)
PORT = 2718


@app.function(max_containers=1, timeout=1_500, gpu="t4")
def run_marimo(timeout: int):
    with modal.forward(PORT) as tunnel:
        marimo_process = subprocess.Popen(
            [
                "marimo",
                "edit",
                "--headless",
                "--host",
                "0.0.0.0",
                "--port",
                str(PORT),
                f"--token-password",
                TOKEN,
                "nbs/notebook.py",
            ],
        )

        print(f"Marimo available at => {tunnel.url}?access_token={TOKEN}")

        try:
            end_time = time.time() + timeout
            while time.time() < end_time:
                time.sleep(5)
            print(
                f"Reached end of {timeout} second timeout period. Exiting..."
            )
        except KeyboardInterrupt:
            print("Exiting...")
        finally:
            marimo_process.kill()


@app.local_entrypoint()
def main():
    run_marimo.remote(1000)
