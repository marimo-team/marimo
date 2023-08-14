import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def __(mo):
    mo.md("# Pokémon Statistics 📊🔬")
    return


@app.cell
def __(mo, pokemon_types):
    mo.md(
        f"""
        Compare Pokémon by primary type, or drill down into
        statistics of individual Pokémon.

        Start by choosing one or more types: {pokemon_types}
        """
    )
    return


@app.cell
def __(pokemon):
    types = pokemon.groupby(["Type 1"])["#"].count()
    types_name = list(types.keys())
    types_name.sort()
    return types, types_name


@app.cell
def __(mo):
    clear_selection = mo.ui.button(label="_Clear selection_")
    return clear_selection,


@app.cell
def __(clear_selection, mo, types_name):
    clear_selection
    pokemon_types = mo.ui.multiselect(types_name)
    return pokemon_types,


@app.cell
def __(mo):
    attribute = mo.ui.dropdown(
        {
            "HP": "HP",
            "Speed": "Speed",
            "Attack": "Attack",
            "Defense": "Defense",
            "Attack / Defense": "Attack / Defense",
            "Sp. Attack": "Sp. Atk",
            "Sp. Defense": "Sp. Def",
            "Sp. Attack / Sp. Defense": "Sp. Atk / Sp. Def",
        }
    )
    return attribute,


@app.cell
def __(clear_selection, mo, pokemon_types):
    mo.hstack(
        [mo.as_html(pokemon_types.value), clear_selection],
        justify="start",
        align="start",
        gap=2,
    ).center() if pokemon_types.value else None
    return


@app.cell
def __(mo, pokemon_types):
    mo.md(
        """
        **Compare distributions** by type or **drill down**
        into specific Pokémon's statistics 👇
        """
    ).callout(kind="alert") if pokemon_types.value else None
    return


@app.cell
def __(pokemon, pokemon_types):
    def get_filtered_pokemon(value):
        if value == "All":
            return pokemon
        else:
            return pokemon[pokemon["Type 1"] == value]

    filtered_pokemons = {}
    for pokemon_type in pokemon_types.value:
        filtered_pokemons[pokemon_type] = get_filtered_pokemon(pokemon_type)
    return filtered_pokemons, get_filtered_pokemon, pokemon_type


@app.cell
def __(distribution_plot, drilldown, mo, pokemon_types):
    mo.tabs(
        {
            "**Compare distributions**": distribution_plot,
            "**Drill down**": drilldown,
        }
    ) if pokemon_types.value else None
    return


@app.cell
def __(plot_pokemon, table):
    _names = [v["Name"] for v in table.value] if table is not None else []
    plot_pokemon(_names) if _names else None
    return


@app.cell
def __(attribute, colors, filtered_pokemons, mo, plt, pokemon_types, sns):
    def plot():
        plt.figure(figsize=(6.5, 4))
        if attribute.value is not None:
            plt.title(attribute.value)
            for ptype, df in filtered_pokemons.items():
                sns.histplot(
                    df[attribute.value],
                    label=ptype,
                    color=colors[ptype],
                    kde=True,
                )
            plt.legend()
            
        return mo.md(
            f"""
            Visualized below is the distribution of {attribute}.

            {mo.as_html(plt.gca())}
            """
        ).center()


    distribution_plot = (
        plot() if pokemon_types.value else None
    )
    return distribution_plot, plot


@app.cell
def __(filtered_pokemons, mo, pokemon_types):
    def make_table():
        records = [
            row
            for df in filtered_pokemons.values()
            for row in df.to_dict(orient="records")
        ]
        return mo.ui.table(records, pagination=True, selection="multi")


    table = make_table() if pokemon_types.value else None
    drilldown = mo.md(
        f"""
        Select one or more Pokémon using the checkboxes. Then scroll down for
        a plot.

        {table}
        """
    )
    return drilldown, make_table, table


@app.cell
def __(pokemon):
    def plot_single_pokemon(ax, angles, labels, name):
        pkmn = pokemon[pokemon.Name == name]

        stats = [
            pkmn["HP"].values[0],
            pkmn["Attack"].values[0],
            pkmn["Defense"].values[0],
            pkmn["Sp. Atk"].values[0],
            pkmn["Sp. Def"].values[0],
            pkmn["Speed"].values[0],
            pkmn["HP"].values[
                0
            ],  # repeat the first value to close the circular graph
        ]
        ax.fill(angles, stats, alpha=0.2, label=name)
        return ax
    return plot_single_pokemon,


@app.cell
def __(np, plot_single_pokemon, plt):
    def plot_pokemon(names):
        fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        labels = np.array(
            ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed", "HP"]
        )
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        ax.set_xticks(angles)
        ax.set_xticklabels(labels)
        for name in names:
            plot_single_pokemon(ax, angles, labels, name)
        plt.legend(loc="upper left")
        return ax
    return plot_pokemon,


@app.cell
def __():
    import marimo as mo
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns

    import os

    print(os.listdir("./input"))

    pokemon = pd.read_csv("./input/Pokemon.csv")
    pokemon["Attack / Defense"] = pokemon["Attack"] / pokemon["Defense"]
    pokemon["Sp. Atk / Sp. Def"] = pokemon["Sp. Atk"] / pokemon["Sp. Def"]
    return mo, np, os, pd, plt, pokemon, sns


@app.cell
def __():
    # Defining colors for graphs
    colors = {
        "Bug": "#A6B91A",
        "Dark": "#705746",
        "Dragon": "#6F35FC",
        "Electric": "#F7D02C",
        "Fairy": "#D685AD",
        "Fighting": "#C22E28",
        "Fire": "#EE8130",
        "Flying": "#A98FF3",
        "Ghost": "#735797",
        "Grass": "#7AC74C",
        "Ground": "#E2BF65",
        "Ice": "#96D9D6",
        "Normal": "#A8A77A",
        "Poison": "#A33EA1",
        "Psychic": "#F95587",
        "Rock": "#B6A136",
        "Steel": "#B7B7CE",
        "Water": "#6390F0",
    }
    return colors,


@app.cell
def __():
    import plotly.express as px
    return px,


if __name__ == "__main__":
    app.run()
