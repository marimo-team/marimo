

import marimo

__generated_with = "0.13.0"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo
    return (mo,)


@app.cell
def _(mo):
    mo.md(
        r"""
        # Hello World in Markdown

        **Bold Text:** Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 

        *Italic Text:* Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 

        ~~Strikethrough~~: Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 

        **Underline Text:** Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 

        <u>Underline Another Way:</u> Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 

        [Link Example](https://www.example.com): Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 

        - **Unordered List:**
          - Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. 
          - Item 2
          - Item 3

        1. **Ordered List:**
           1. Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book.
           2. Second Item
           3. Third Item

        > **Blockquote:** Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book.

        `Inline Code:` Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book.

        ```
        Code Block:
        For longer code examples, use triple backticks.
        def hello_world():
            print("Hello, World!")
        ```

        **Image:**

        ![Alt Text for Image](https://placehold.co/800x400)

        **Horizontal Rule:**

        ---

        Use hyphens (`---`), asterisks (`***`), or underscores (`___`) to create horizontal rules.

        **Table:**

        | Header 1 | Header 2 | Header 3 |
        |:--------:|:--------:|:--------:|
        | Row 1, Col 1 Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text | Row 1, Col 2 | Row 1, Col 3 |
        | Row 2, Col 1 | Row 2, Col 2 | Row 2, Col 3 |
        """
    )
    return


@app.cell
def _(mo):
    mo.md(r"""This cell now contains a link to [marimo](https://docs.marimo.io/), and suddenly all sort of weird things are happening - line widths change, and there is no lie wrap anymore!""")
    return


if __name__ == "__main__":
    app.run()
