import marimo

__generated_with = "0.19.7"
app = marimo.App()


@app.cell
def _(Aframe, xyz):
    a = Aframe()
    a.set_scene(
        background="color: #ECECEC; fog: type: exponential; color: #AAA; density: 0.05"
    )
    a.sky(color="#ECECEC")
    a.box(
        position=xyz(-1, 0.5, -3),
        rotation=xyz(0, 45, 0),
        color="#4CC3D9",
        shadow=True,
        animation="property: rotation; to: 0 405 0; loop: true; dur: 10000",
    )
    a.sphere(
        position=xyz(0, 1.25, -5),
        radius=1.25,
        color="#EF2D5E",
        shadow=True,
        animation="property: position; to: 0 2.5 -5; dir: alternate; loop: true; dur: 2000; easing: easeInOutSine",
    )
    a.cylinder(
        position=xyz(1, 0.75, -3),
        radius=0.5,
        height=1.5,
        color="#FFC65D",
        shadow=True,
        animation="property: rotation; to: 0 360 0; loop: true; dur: 8000",
    )
    a.plane(
        position=xyz(0, 0, -4),
        rotation=xyz(-90, 0, 0),
        width=4,
        height=4,
        color="#7BC8A4",
        repeat="4 4",
    )
    a.light(type="ambient", color="#445451")
    a.light(type="point", intensity=0.5, position=xyz(2, 4, -2))
    a.camera(position=xyz(0, 1.6, 0))
    return (a,)


@app.cell
def _(a, mo):
    mo.iframe(a.generate())
    return


@app.cell
def _():
    import marimo as mo
    from aframe import Aframe, xyz

    return Aframe, mo, xyz


if __name__ == "__main__":
    app.run()
