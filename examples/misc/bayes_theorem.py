import marimo

__generated_with = "0.2.5"
app = marimo.App(width="full")


@app.cell
def __(mo):
    mo.md(
        r"""
        # Bayes' Theorem

        _This interactive notebook was made with [marimo](https://github.com/marimo-team/marimo), and is [based on an explanation of Bayes' Theorem by Grant Sanderson](https://www.youtube.com/watch?v=HZGCoVF3YvM&list=PLzq7odmtfKQw2KIbQq0rzWrqgifHKkPG1&index=1&t=3s)_.

        Bayes theorem provides a convenient way to calculate the probability
        of a hypothesis event $H$ given evidence $E$:

        \[
        P(H \mid E) = \frac{P(H) P(E \mid H)}{P(E)}.
        \]


        **The numerator.** The numerator is the probability of events $E$ and $H$ happening
        together; that is,
        
        \[
           P(H) P(E \mid H) = P(E \cap H).
        \]
        
        **The denominator.**
        In most calculations, it is helpful to rewrite the denominator $P(E)$ as 
        
        \[
        P(E) = P(H)P(E \mid H) + P(\neg H) P (E \mid \neg H),
        \]
        
        which in turn can also be written as

        
        \[
        P(E) = P(E \cap H) + P(E \cap \neg H).
        \]
        """
    ).left()
    return


@app.cell
def __(mo):
    p_h = mo.ui.slider(0.0, 1, label="$P(H)$", value=0.1, step=0.1)
    p_e_given_h = mo.ui.slider(0.0, 1, label="$P(E \mid H)$", value=0.3, step=0.1)
    p_e_given_not_h = mo.ui.slider(
        0.0, 1, label=r"$P(E \mid \neg H)$", value=0.3, step=0.1
    )
    return p_e_given_h, p_e_given_not_h, p_h


@app.cell
def __(p_e_given_h, p_e_given_not_h, p_h):
    p_e = p_h.value*p_e_given_h.value + (1 - p_h.value)*p_e_given_not_h.value
    bayes_result = p_h.value * p_e_given_h.value / p_e
    return bayes_result, p_e


@app.cell
def __(
    bayes_result,
    construct_probability_plot,
    mo,
    p_e,
    p_e_given_h,
    p_e_given_not_h,
    p_h,
):
    mo.hstack(
        [
            mo.md(
                rf"""
                ## Probabilities

                You can configure the probabilities of the events $H$, $E \mid H$, and $E \mid \neg H$

                {mo.as_html([p_h, p_e_given_h, p_e_given_not_h])}

                The plot on the right visualizes the probabilities of these events. 
                
                1. The yellow rectangle represents the event $H$, and its area is $P(H) = {p_h.value:0.2f}$.
                2. The teal rectangle overlapping with the yellow one represents the event $E \cap H$, and
                   its area is $P(H) \cdot P(E \mid H) = {p_h.value * p_e_given_h.value:0.2f}$.
                3. The teal rectangle that doesn't overlap the yellow rectangle represents the event $E \cap \neg H$, and
                   its area is $P(\neg H) \cdot P(E \mid \neg H) = {(1 - p_h.value) * p_e_given_not_h.value:0.2f}$.

                Notice that the sum of the areas in $2$ and $3$ is the probability $P(E) = {p_e:0.2f}$. 
                
                One way to think about Bayes' Theorem is the following: the probability $P(H \mid E)$ is the probability
                of $E$ and $H$ happening together (the area of the rectangle $2$), divided by the probability of $E$ happening
                at all (the sum of the areas of $2$ and $3$).
                In this case, Bayes' Theorem says
                
                \[
                P(H \mid E) = \frac{{P(H) P(E \mid H)}}{{P(E)}} = \frac{{{p_h.value} \cdot {p_e_given_h.value}}}{{{p_e:0.2f}}} = {bayes_result:0.2f}
                \]
                """
            ),
            construct_probability_plot(),
        ],
        justify="start",
        gap=4,
        align="start",
        widths=[0.33, 0.5],
    )
    return


@app.cell
def __(p_e_given_h, p_e_given_not_h, p_h):
    def construct_probability_plot():
        import matplotlib.pyplot as plt

        plt.axes()

        # Radius: 1, face-color: red, edge-color: blue
        plt.figure(figsize=(6,6))
        base = plt.Rectangle((0, 0), 1, 1, fc="black", ec="white", alpha=0.25)
        h = plt.Rectangle((0, 0), p_h.value, 1, fc="yellow", ec="white", label="H")
        e_given_h = plt.Rectangle(
            (0, 0),
            p_h.value,
            p_e_given_h.value,
            fc="teal",
            ec="white",
            alpha=0.5,
            label="E",
        )
        e_given_not_h = plt.Rectangle(
            (p_h.value, 0), 1 - p_h.value, p_e_given_not_h.value, fc="teal", ec="white", alpha=0.5
        )
        plt.gca().add_patch(base)
        plt.gca().add_patch(h)
        plt.gca().add_patch(e_given_not_h)
        plt.gca().add_patch(e_given_h)
        plt.legend()
        return plt.gca()
    return construct_probability_plot,


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
