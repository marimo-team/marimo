# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "fastapi",
#     "marimo",
#     "starlette",
#     "matplotlib==3.10.0",
#     "pillow==11.1.0",
# ]
# ///
import marimo
import fastapi

from fastapi import FastAPI, Request
import logging

from fastapi.responses import HTMLResponse, StreamingResponse

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a FastAPI app
app = FastAPI()


@app.get("/add/{a}/{b}")
async def add_endpoint(request: Request, a: int, b: int) -> int:
    from notebook import add

    # We grab the function from the definition
    # and call it with the a and b arguments
    return add(a, b)


@app.get("/greet")
async def greet(request: Request):
    from notebook import greet

    name = request.query_params.get("name")

    # We grab the function from the definition
    # and call it with the name argument
    return greet(name)


@app.get("/plot")
async def plot(request: Request):
    from notebook import plot
    import json
    from PIL import Image
    import io

    try:
        data = json.loads(request.query_params.get("data"))
    except Exception as e:
        data = {
            "2019": 150,
            "2020": 200,
            "2021": 180,
            "2022": 250,
            "2023": 300,
        }

    # Get the image from the notebook,
    # which is the output of the plot function
    output: Image.Image
    # We override the plot_data argument
    # to use the data passed in the query string
    output, _ = plot.run(plot_data=data)

    # Save the image to a BytesIO object
    buf = io.BytesIO()
    output.save(buf, format="PNG")
    buf.seek(0)

    # Return the image as a StreamingResponse
    return StreamingResponse(
        content=buf,
        media_type="image/png",
    )


@app.get("/")
async def home(request: Request):
    return HTMLResponse(
        f"""
        This example shows how to use marimo notebooks as API endpoints in a FastAPI app.
        <br/>
        using marimo {marimo.__version__} and fastapi {fastapi.__version__}
        <br/>

        Try these endpoints:
        <ul>
            <li><a target="_blank" href="/add/1/2">Add two numbers: /add/1/2</a></li>
            <li><a target="_blank" href="/greet?name=World">Get a greeting: /greet?name=World</a></li>
            <li><a target="_blank" href="/plot?data=%7B%222019%22%3A%20150%2C%20%222020%22%3A%20200%2C%20%222021%22%3A%20180%2C%20%222022%22%3A%20250%2C%20%222023%22%3A%20300%7D">Plot a dictionary: /plot?data=%7B%222019%22%3A%20150%2C%20%222020%22%3A%20200%2C%20%222021%22%3A%20180%2C%20%222022%22%3A%20250%2C%20%222023%22%3A%20300%7D</a></li>
        </ul>
        """
    )


# Run the server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8000, log_level="info")
