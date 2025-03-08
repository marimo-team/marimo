import marimo

__generated_with = "0.10.15"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Task List

        - item
        -   [X] item 1
            *   [X] item A
            *   [ ] item B
                more text
                +   [x] item a
                +   [ ] item b
                +   [x] item c
            *   [X] item C
            *   non item
        -   [ ] item 2
        -   [ ] item 3
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Base 64

        ![picture](../../docs/_static/docs-settings.png)
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Admonitions

        !!! important ""
            This is an admonition box without a title.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Caption

        Fruit      | Amount
        ---------- | ------
        Apple      | 20
        Peach      | 10
        Banana     | 3
        Watermelon | 1

        /// caption
        Fruit Count
        ///
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Tabs

        /// tab | Tab 1 title
        Tab 1 content
        ///

        /// tab | Tab 2 title
        Tab 2 content
        ///
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        """
        ## Details

        /// details | Basic details
        This is a basic details section
        ///

        /// details | Info details
            type: info

        This shows important information
        ///

        /// details | Warning details  
            type: warn

        This highlights something to watch out for
        ///

        /// details | Danger details
            type: danger

        This indicates a critical warning or dangerous situation
        ///

        /// details | Success details
            type: success

        This indicates a successful outcome or positive note
        ///
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Nested em

        This * won't emphasize *

        This *will emphasize*

        ***I'm italic and bold* I am just bold.**

        ***I'm bold and italic!** I am just italic.*
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Critic

        Here is some {--*incorrect*--} Markdown.  I am adding this{++ here++}.  Here is some more {--text
         that I am removing--}text.  And here is even more {++text that I 
         am ++}adding.{~~

        ~>  ~~}Paragraph was deleted and replaced with some spaces.{~~  ~>

        ~~}Spaces were removed and a paragraph was added.

        And here is a comment on {==some
         text==}{>>This works quite well. I just wanted to comment on it.<<}. Substitutions {~~is~>are~~} great!

        General block handling.

        {--

        * test remove
        * test remove
        * test remove
            * test remove
        * test remove

        --}

        {++

        * test add
        * test add
        * test add
            * test add
        * test add

        ++}
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Emoji

        :smile: :heart: :thumbsup:
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Keys

        ++ctrl+alt+delete++
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Magic link

        - Just paste links directly in the document like this: https://google.com.
        - Or even an email address: fake.email@email.com.
        """
    )
    return


@app.cell
def _(mo):
    mo.md(
        r"""
        ## Subscripts and strikethrough

        ~~Delete me~~

        CH~3~CH~2~OH

        text~a\ subscript~
        """
    )
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
