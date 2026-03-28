import marimo

__generated_with = "0.13.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import cProfile
    import struct
    import os

    mo.md("# Binary File Download Test (GH-5361)\n\nUse the **file explorer** panel on the left to navigate into the smoke test directory and try downloading the sample files. Binary files (`.prof`, `.bin`, `.pkl`, `.png`) should download as valid binary, not as base64 text.")
    return cProfile, mo, os, struct


@app.cell
def _(cProfile, os, struct):
    import pickle
    import zlib

    test_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. cProfile .prof file
    prof_path = os.path.join(test_dir, "sample.prof")
    profiler = cProfile.Profile()
    profiler.enable()
    sum(range(10000))
    profiler.disable()
    profiler.dump_stats(prof_path)

    # 2. Generic binary file with non-UTF8 bytes
    bin_path = os.path.join(test_dir, "sample.bin")
    with open(bin_path, "wb") as f:
        f.write(struct.pack("!4sIf16s", b"MAGIC", 42, 3.14, b"\xff\xfe\xfd" + b"\x00" * 13))

    # 3. Pickle file
    pkl_path = os.path.join(test_dir, "sample.pkl")
    with open(pkl_path, "wb") as f:
        pickle.dump({"key": "value", "numbers": [1, 2, 3], "bytes": b"\xff\xfe"}, f)

    # 4. A plain text file (control: should still work)
    txt_path = os.path.join(test_dir, "sample.txt")
    with open(txt_path, "w") as f:
        f.write("This is a plain text file.\nIt should download correctly.\n")

    # 5. A minimal valid PNG (1x1 red pixel) — tests the isMediaMime/dataURL path
    def _make_png():
        def chunk(ctype, data):
            c = ctype + data
            return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
            + chunk(b"IEND", b"")
        )

    png_path = os.path.join(test_dir, "sample.png")
    with open(png_path, "wb") as f:
        f.write(_make_png())

    print(f"Created test files in {test_dir}:")
    for name in ["sample.prof", "sample.bin", "sample.pkl", "sample.txt", "sample.png"]:
        p = os.path.join(test_dir, name)
        print(f"  {name}: {os.path.getsize(p)} bytes")
    return


if __name__ == "__main__":
    app.run()
