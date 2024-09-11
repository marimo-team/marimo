# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
# ]
# ///
# Copyright 2024 Marimo. All rights reserved.
import marimo

__generated_with = "0.1.76"
app = marimo.App()


@app.cell
def __(mo):
    mo.ui.code_editor("print(2 + 2)", min_height=50)
    return


@app.cell
def __(mo):
    mo.ui.code_editor("SELECT * FROM table;", language="sql", theme="light")
    return


@app.cell(hide_code=True)
def __(languages, mo):
    language_select = mo.ui.dropdown(
        languages,
        value="javascript",
        label="Language",
        full_width=True,
    )
    theme_select = mo.ui.radio(["light", "dark"], value="dark", label="Theme")
    mo.hstack([language_select, theme_select], justify="start", gap=2)
    return language_select, theme_select


@app.cell
def __(language_select, mo, samples, theme_select):
    mo.ui.code_editor(
        samples[language_select.value],
        language=language_select.value,
        theme=theme_select.value,
    )
    return


@app.cell
def __():
    languages = ["sql", "python", "javascript", "ruby", "c", "java", "go"]
    samples = {
        "sql": "SELECT * FROM table;",
        "python": "print(2 + 2)",
        "javascript": "console.log(2 + 2)",
        "ruby": "puts 2 + 2",
        "c": 'printf("%d", 2 + 2);',
        "c++": "cout << 2 + 2 << endl;",
        "c#": "Console.WriteLine(2 + 2);",
        "java": "System.out.println(2 + 2);",
        "go": "fmt.Println(2 + 2)",
    }
    return languages, samples


@app.cell
def __():
    import marimo as mo
    return mo,


if __name__ == "__main__":
    app.run()
