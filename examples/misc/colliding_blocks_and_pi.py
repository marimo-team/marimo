# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "marimo",
#     "matplotlib==3.10.1",
#     "numpy==2.2.3",
# ]
# ///

import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Finding $\pi$ in colliding blocks

    One of the remarkable things about mathematical constants like $\pi$ is how frequently they arise in nature, in the most surprising of places.

    Inspired by 3Blue1Brown, this [marimo notebook](https://github.com/marimo-team/marimo) shows how the number of collisions incurred in a particular system involving two blocks converges to the digits in $\pi$.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    slider = mo.ui.slider(start=0, stop=3, value=3, show_value=True)
    return (slider,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Simulate!
    """)
    return


@app.cell(hide_code=True)
def _(mo, slider):
    mo.md(f"Use this slider to control the weight of the heavier block: {slider}")
    return


@app.cell(hide_code=True)
def _(mo, slider):
    mo.md(rf"The heavier block weighs **$100^{{ {slider.value} }}$** kg.")
    return


@app.cell(hide_code=True)
def _(mo):
    run_button = mo.ui.run_button(label="Run simulation!")
    run_button.right()
    return (run_button,)


@app.cell
def _(run_button, simulate_collisions, slider):
    if run_button.value:
        mass_ratio = 100**slider.value
        _, ani, collisions = simulate_collisions(
            mass_ratio, total_time=15, dt=0.001
        )
    return (ani,)


@app.cell
def _(ani, mo, run_button):
    video = None
    if run_button.value:
        with mo.status.spinner(title="Rendering collision video ..."):
            video = mo.Html(ani.to_html5_video())
    video
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## The 3Blue1Brown video

    If you haven't seen it, definitely check out the video that inspired this notebook:
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.accordion(
        {
            "🎥 Watch the video": mo.Html(
                '<iframe width="700" height="400" src="https://www.youtube.com/embed/6dTyOl1fmDo?si=xl9v6Y8x2e3r3A9I" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>'
            )
        }
    )
    return


@app.cell
def _():
    import numpy as np
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.patches import Rectangle

    return Rectangle, animation, plt


@app.class_definition
class Block:
    def __init__(self, mass, velocity, position, size=1.0):
        self.mass = mass
        self.velocity = velocity
        self.position = position
        self.size = size

    def update(self, dt):
        self.position += self.velocity * dt

    def collide(self, other):
        # Calculate velocities after elastic collision
        m1, m2 = self.mass, other.mass
        v1, v2 = self.velocity, other.velocity

        new_v1 = (m1 - m2) / (m1 + m2) * v1 + (2 * m2) / (m1 + m2) * v2
        new_v2 = (2 * m1) / (m1 + m2) * v1 + (m2 - m1) / (m1 + m2) * v2

        self.velocity = new_v1
        other.velocity = new_v2

        return 1


@app.function
def check_collisions(small_block, big_block, wall_pos=0):
    collisions = 0

    # Check for collision between blocks
    if small_block.position + small_block.size > big_block.position:
        small_block.position = big_block.position - small_block.size
        collisions += small_block.collide(big_block)

    # Check for collision with the wall
    if small_block.position < wall_pos:
        small_block.position = wall_pos
        small_block.velocity *= -1
        collisions += 1

    return collisions


@app.cell
def _(create_animation):
    def simulate_collisions(mass_ratio, total_time=15, dt=0.001, animate=True):
        # Initialize blocks
        small_block = Block(mass=1, velocity=0, position=2)
        big_block = Block(mass=mass_ratio, velocity=-0.5, position=4)

        # Simulation variables
        time = 0
        collision_count = 0

        # For animation
        times = []
        small_positions = []
        big_positions = []
        collision_counts = []

        # Run simulation
        while time < total_time:
            # Update positions
            small_block.update(dt)
            big_block.update(dt)

            # Check for and handle collisions
            new_collisions = check_collisions(small_block, big_block)
            collision_count += new_collisions

            # Store data for animation
            times.append(time)
            small_positions.append(small_block.position)
            big_positions.append(big_block.position)
            collision_counts.append(collision_count)

            time += dt

        print(f"Mass ratio: {mass_ratio}, Total collisions: {collision_count}")

        if animate:
            axis, ani = create_animation(
                times, small_positions, big_positions, collision_counts, mass_ratio
            )
        else:
            axis, ani = None

        return axis, ani, collision_count

    return (simulate_collisions,)


@app.cell
def _(Rectangle, animation, plt):
    def create_animation(
        times, small_positions, big_positions, collision_counts, mass_ratio
    ):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Setup for blocks visualization
        ax1.set_xlim(-1, 10)
        ax1.set_ylim(-1, 2)
        ax1.set_xlabel("Position")
        ax1.set_title(f"Block Collisions (Mass Ratio = {mass_ratio})")
        wall = plt.Line2D([0, 0], [-1, 2], color="black", linewidth=3)
        ax1.add_line(wall)

        small_block = Rectangle((small_positions[0], 0), 1, 1, color="blue")
        big_block = Rectangle((big_positions[0], 0), 1, 1, color="red")
        ax1.add_patch(small_block)
        ax1.add_patch(big_block)

        # Add weight labels for each block
        small_label = ax1.text(
            small_positions[0] + 0.5,
            1.2,
            f"{1}kg",
            ha="center",
            va="center",
            color="blue",
            fontweight="bold",
        )
        big_label = ax1.text(
            big_positions[0] + 0.5,
            1.2,
            f"{mass_ratio}kg",
            ha="center",
            va="center",
            color="red",
            fontweight="bold",
        )

        # Setup for collision count
        ax2.set_xlim(0, times[-1])
        # ax2.set_ylim(0, collision_counts[-1] * 1.1)
        ax2.set_ylim(0, collision_counts[-1] * 1.1)
        ax2.set_xlabel("Time")
        ax2.set_ylabel("# Collisions:")
        ax2.set_yscale("symlog")
        (collision_line,) = ax2.plot([], [], "g-")

        # Add text for collision count
        collision_text = ax2.text(
            0.02, 0.9, "", transform=ax2.transAxes, fontsize="x-large"
        )

        def init():
            small_block.set_xy((small_positions[0], 0))
            big_block.set_xy((big_positions[0], 0))
            small_label.set_position((small_positions[0] + 0.5, 1.2))
            big_label.set_position((big_positions[0] + 0.5, 1.2))
            collision_line.set_data([], [])
            collision_text.set_text("")
            return small_block, big_block, collision_line, collision_text

        frame_step = 300

        def animate(i):
            # Speed up animation but ensure we reach the final frame
            frame_index = min(i * frame_step, len(times) - 1)

            small_block.set_xy((small_positions[frame_index], 0))
            big_block.set_xy((big_positions[frame_index], 0))

            # Update the weight labels to follow the blocks
            small_label.set_position((small_positions[frame_index] + 0.5, 1.2))
            big_label.set_position((big_positions[frame_index] + 0.5, 1.2))

            # Show data up to the current frame
            collision_line.set_data(
                times[: frame_index + 1], collision_counts[: frame_index + 1]
            )

            # For the last frame, show the final collision count
            if frame_index >= len(times) - 1:
                collision_text.set_text(f"# Collisions: {collision_counts[-1]}")
            else:
                collision_text.set_text(
                    f"# Collisions: {collision_counts[frame_index]}"
                )

            return (
                small_block,
                big_block,
                small_label,
                big_label,
                collision_line,
                collision_text,
            )

        plt.tight_layout()

        frames = max(1, len(times) // frame_step)  # Ensure at least 1 frame
        ani = animation.FuncAnimation(
            fig,
            animate,
            frames=frames + 1,  # +1 to ensure we reach the end
            init_func=init,
            blit=True,
            interval=30,
        )

        plt.tight_layout()
        return plt.gca(), ani

        # Uncomment to save animation
        # ani.save('pi_collisions.mp4', writer='ffmpeg', fps=30)
    return (create_animation,)


if __name__ == "__main__":
    app.run()
