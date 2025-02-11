# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "marimo",
#     "matplotlib==3.10.0",
#     "pillow==11.1.0",
# ]
# ///

import marimo

__generated_with = "0.11.2"
app = marimo.App()


@app.cell
def add():
    def add(a: int, b: int) -> int:
        """Add two numbers together"""
        return a + b

    return (add,)


@app.cell
def greet():
    def greet(name: str) -> str:
        """Return a greeting message"""
        return f"Hello {name}!"

    return (greet,)


@app.cell
def fibonacci():
    def fibonacci(n: int) -> list[int]:
        """Return first n numbers of Fibonacci sequence"""
        if n <= 0:
            return []
        elif n == 1:
            return [0]

        sequence = [0, 1]
        while len(sequence) < n:
            sequence.append(sequence[-1] + sequence[-2])
        return sequence

    return (fibonacci,)


@app.cell
def _():
    import matplotlib.pyplot as plt
    from PIL import Image

    return Image, plt


@app.cell
def plot(Image, plot_data, plt):
    def plot_dictionary(data: dict) -> None:
        """Plot dictionary items as a bar chart"""
        # Clear any existing plots
        plt.clf()

        # Create figure with higher DPI
        fig = plt.figure(figsize=(10, 6), dpi=100)
        plt.bar(list(data.keys()), list(data.values()))
        plt.xticks(rotation=45)
        plt.xlabel("Items")
        plt.ylabel("Values")
        plt.title("Dictionary Items Plot")
        plt.tight_layout()

        # Convert to PIL Image with proper size preservation
        canvas = fig.canvas
        canvas.draw()
        width, height = fig.get_size_inches() * fig.get_dpi()
        image = Image.frombytes(
            "RGBA", (int(width), int(height)), canvas.buffer_rgba()
        )
        plt.close(fig)  # Clean up
        return image

    plot_dictionary(plot_data)
    return (plot_dictionary,)


@app.cell(hide_code=True)
def _():
    # Fallback data
    plot_data = {
        "2019": 150,
        "2020": 200,
        "2021": 180,
        "2022": 250,
        "2023": 300,
    }
    return (plot_data,)


@app.cell(hide_code=True)
def _(plot_dictionary):
    # Example usage of plot_dictionary
    sample_data = {
        "Apple": 30,
        "Banana": 25,
        "Orange": 40,
        "Mango": 15,
        "Grapes": 35,
    }

    plot_dictionary(sample_data)
    return (sample_data,)


@app.cell
def stats():
    def stats(numbers: list[float]) -> dict:
        """Calculate basic statistics for a list of numbers"""
        if not numbers:
            return {"mean": None, "min": None, "max": None}
        return {
            "mean": sum(numbers) / len(numbers),
            "min": min(numbers),
            "max": max(numbers),
        }

    return (stats,)


if __name__ == "__main__":
    app.run()
