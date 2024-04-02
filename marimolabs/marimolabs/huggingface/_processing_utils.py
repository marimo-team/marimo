import base64
import hashlib
from pathlib import Path

import httpx
from marimolabs.huggingface import _client_utils


def hash_base64(base64_encoding: str, chunk_num_blocks: int = 128) -> str:
    sha1 = hashlib.sha1()
    for i in range(
        0, len(base64_encoding), chunk_num_blocks * sha1.block_size
    ):
        data = base64_encoding[i : i + chunk_num_blocks * sha1.block_size]
        sha1.update(data.encode("utf-8"))
    return sha1.hexdigest()


def save_base64_to_cache(
    base64_encoding: str, cache_dir: str, file_name: str | None = None
) -> str:
    """Converts a base64 encoding to a file and returns the path to the file if
    the file doesn't already exist. Otherwise returns the path to the existing file.
    """
    temp_dir = hash_base64(base64_encoding)
    temp_dir = Path(cache_dir) / temp_dir
    temp_dir.mkdir(exist_ok=True, parents=True)

    guess_extension = _client_utils.get_extension(base64_encoding)
    if file_name:
        file_name = _client_utils.strip_invalid_filename_characters(file_name)
    elif guess_extension:
        file_name = f"file.{guess_extension}"
    else:
        file_name = "file"

    full_temp_file_path = str(abspath(temp_dir / file_name))  # type: ignore

    if not Path(full_temp_file_path).exists():
        data, _ = _client_utils.decode_base64_to_binary(base64_encoding)
        with open(full_temp_file_path, "wb") as fb:
            fb.write(data)

    return full_temp_file_path


def extract_base64_data(x: str) -> str:
    """Just extracts the base64 data from a general base64 string."""
    return x.rsplit(",", 1)[-1]


def to_binary(x: str | dict) -> bytes:
    """Converts a base64 string or dictionary to a binary string that can be sent in a POST."""
    if isinstance(x, dict):
        if x.get("data"):
            base64str = x["data"]
        else:
            base64str = _client_utils.encode_url_or_file_to_base64(x["path"])
    else:
        base64str = x
    return base64.b64decode(extract_base64_data(base64str))


def encode_to_base64(r: httpx.Response) -> str:
    # Handles the different ways HF API returns the prediction
    base64_repr = base64.b64encode(r.content).decode("utf-8")
    data_prefix = ";base64,"
    # Case 1: base64 representation already includes data prefix
    if data_prefix in base64_repr:
        return base64_repr
    else:
        content_type = r.headers.get("content-type")
        # Case 2: the data prefix is a key in the response
        if content_type == "application/json":
            try:
                data = r.json()[0]
                content_type = data["content-type"]
                base64_repr = data["blob"]
            except KeyError as ke:
                raise ValueError(
                    "Cannot determine content type returned by external API."
                ) from ke
        # Case 3: the data prefix is included in the response headers
        else:
            pass
        new_base64 = f"data:{content_type};base64,{base64_repr}"
        return new_base64
