import base64
import mimetypes
import secrets
import tempfile
from pathlib import Path


def get_extension(encoding: str) -> str | None:
    encoding = encoding.replace("audio/wav", "audio/x-wav")
    type = mimetypes.guess_type(encoding)[0]
    if type == "audio/flac":  # flac is not supported by mimetypes
        return "flac"
    elif type is None:
        return None
    extension = mimetypes.guess_extension(type)
    if extension is not None and extension.startswith("."):
        extension = extension[1:]
    return extension


def strip_invalid_filename_characters(
    filename: str, max_bytes: int = 200
) -> str:
    """Strips invalid characters from a filename and ensures that the file_length is less than `max_bytes` bytes."""
    filename = "".join(
        [char for char in filename if char.isalnum() or char in "._- "]
    )
    filename_len = len(filename.encode())
    if filename_len > max_bytes:
        while filename_len > max_bytes:
            if len(filename) == 0:
                break
            filename = filename[:-1]
            filename_len = len(filename.encode())
    return filename


def decode_base64_to_binary(encoding: str) -> tuple[bytes, str | None]:
    extension = get_extension(encoding)
    data = encoding.rsplit(",", 1)[-1]
    return base64.b64decode(data), extension


def decode_base64_to_file(
    encoding: str,
    file_path: str | None = None,
    dir: str | Path | None = None,
    prefix: str | None = None,
):
    directory = Path(dir or tempfile.gettempdir()) / secrets.token_hex(20)
    directory.mkdir(exist_ok=True, parents=True)
    data, extension = decode_base64_to_binary(encoding)
    if file_path is not None and prefix is None:
        filename = Path(file_path).name
        prefix = filename
        if "." in filename:
            prefix = filename[0 : filename.index(".")]
            extension = filename[filename.index(".") + 1 :]

    if prefix is not None:
        prefix = strip_invalid_filename_characters(prefix)

    if extension is None:
        file_obj = tempfile.NamedTemporaryFile(
            delete=False, prefix=prefix, dir=directory
        )
    else:
        file_obj = tempfile.NamedTemporaryFile(
            delete=False,
            prefix=prefix,
            suffix="." + extension,
            dir=directory,
        )
    file_obj.write(data)
    file_obj.flush()
    return file_obj
