import marimo

__generated_with = "0.20.1"
app = marimo.App()


@app.cell
def _():
    import marimo as mo
    import random
    import time
    import threading

    return mo, random, threading, time


@app.cell
def _(mo, random, threading, time):
    def step(pbar: mo.status.progress_bar, work: int):
        for _ in range(work):
            # Sleep... or anything else that releases GIL
            time.sleep(random.uniform(0.5, 1))
            pbar.update(
                subtitle=f"work completed by thread {threading.get_ident()}"
            )

    return (step,)


@app.cell
def _(mo, random, step, time):
    total = 30
    with mo.status.progress_bar(total=total) as pbar:
        n_threads = 4
        work = total // n_threads
        remainder = total % n_threads
        threads = [
            mo.Thread(target=step, args=(pbar, work))
            for _ in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        for _ in range(remainder):
            time.sleep(random.uniform(0.5, 1))
            pbar.update(subtitle="work completed by main thread")
    return


if __name__ == "__main__":
    app.run()
