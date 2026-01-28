import marimo

__generated_with = "0.19.4"
app = marimo.App(width="medium")


@app.cell
def _(mo):
    mo.md(r"""
    # hello
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    This is `inline code`
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ```python
    def fibonacci(n):
        if n <= 0:
            return []
        elif n == 1:
            return [0]
        elif n == 2:
            return [0, 1]

        fib_sequence = [0, 1]
        for i in range(2, n):
            fib_sequence.append(fib_sequence[i-1] + fib_sequence[i-2])

        return fib_sequence
    ```
    """)
    return


@app.cell(hide_code=True)
def _(code_block, mo):
    mo.md(rf"""
    ```
    # Example usage:
    # print(fibonacci(10))
    ```

    **Nested code block**
    {code_block}
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    code_block=mo.md("""
    ```python
    def add(x: int, y: int):
        return x + y
    ```
    """)
    return (code_block,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Nested Markdown Edge Cases

    The following cells test various edge cases for nested `mo.md()` calls,
    which rely on the `__format__` method returning rendered HTML without
    flattening. See #6464 and #7931.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Deeply nested mo.md() - 3 levels
    inner = mo.md("""
    ```sql
    SELECT * FROM users WHERE active = true;
    ```
    """)

    middle = mo.md(f"""
    **Query example:**
    {inner}
    """)

    mo.md(f"""
    ### Triple Nested Markdown

    Here's a deeply nested structure:

    {middle}

    The SQL code block above went through 3 levels of nesting.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Multiple code blocks with different languages in one nested call
    python_code = mo.md("""
    ```python
    async def fetch_data(url: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.json()
    ```
    """)

    js_code = mo.md("""
    ```javascript
    const fetchData = async (url) => {
        const response = await fetch(url);
        return response.json();
    };
    ```
    """)

    mo.md(f"""
    ### Multiple Languages Side by Side

    **Python version:**
    {python_code}

    **JavaScript version:**
    {js_code}
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Code block with backticks inside (escaped)
    nested_backticks = mo.md(r"""
    ```markdown
    Use `inline code` or code blocks:

    ```python
    print("nested fence")
    ```
    ```
    """)

    mo.md(f"""
    ### Nested Backticks

    This tests code blocks that contain backticks:

    {nested_backticks}
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # HTML inside nested markdown
    html_content = mo.md("""
    <div style="background: #f0f0f0; padding: 10px; border-radius: 4px;">
        <strong>Custom HTML Box</strong>
        <p>This is a paragraph inside HTML.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
    </div>
    """)

    mo.md(f"""
    ### Nested HTML Inside Markdown

    Raw HTML should be preserved when nested:

    {html_content}

    Text continues after the HTML block.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Code block with special characters and indentation
    indented_code = mo.md("""
    ```yaml
    services:
      web:
        build: .
        ports:
          - "8000:8000"
        environment:
          DATABASE_URL: "postgres://user:pass@db/app"
          SECRET_KEY: "${SECRET_KEY}"
    ```
    """)

    mo.md(f"""
    ### Preserved Indentation

    YAML requires precise indentation:

    {indented_code}

    The indentation should be exactly preserved.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Nested markdown with tables
    table_md = mo.md("""
    | Function | Complexity | Notes |
    |----------|------------|-------|
    | `sort()` | O(n log n) | Timsort |
    | `search()` | O(log n) | Binary search |
    | `insert()` | O(n) | Array shift |
    """)

    mo.md(f"""
    ### Nested Tables

    Tables should render correctly when nested:

    {table_md}

    Tables with backticks in cells are especially tricky.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Nested lists with code blocks
    list_with_code = mo.md("""
    1. First, define your function:
       ```python
       def greet(name):
           return f"Hello, {name}!"
       ```

    2. Then call it:
       ```python
       result = greet("World")
       print(result)  # Hello, World!
       ```

    3. Handle edge cases:
       ```python
       def greet(name):
           if not name:
               raise ValueError("Name required")
           return f"Hello, {name}!"
       ```
    """)

    mo.md(f"""
    ### Lists Containing Code Blocks

    Numbered lists with embedded code:

    {list_with_code}
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Multiple nested blocks in sequence
    block1 = mo.md("```\nBlock 1\n```")
    block2 = mo.md("```\nBlock 2\n```")
    block3 = mo.md("```\nBlock 3\n```")

    mo.md(f"""
    ### Multiple Sequential Nested Blocks

    {block1}

    {block2}

    {block3}

    All three blocks should render as separate code blocks.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Edge case: empty code block
    empty_block = mo.md("""
    ```
    ```
    """)

    mo.md(f"""
    ### Empty Code Block

    An empty code block:

    {empty_block}

    Should render as an empty code block, not disappear.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Edge case: code block with only whitespace
    whitespace_block = mo.md("""
    ```


    ```
    """)

    mo.md(f"""
    ### Whitespace-Only Code Block

    A code block with only whitespace:

    {whitespace_block}

    Should preserve the whitespace.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Nested callout containing code
    code_in_callout = mo.md("""
    ```python
    # Important: Always validate input
    def process(data: dict) -> dict:
        if not isinstance(data, dict):
            raise TypeError("Expected dict")
        return {k: v.strip() for k, v in data.items()}
    ```
    """)

    mo.callout(
        mo.md(f"""
        **Best Practice**

        {code_in_callout}

        Always validate your inputs!
        """),
        kind="warn",
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # Combining mo.md with mo.accordion
    section1 = mo.md("""
    ```python
    def method_one():
        '''Simple approach'''
        return [x**2 for x in range(10)]
    ```
    """)

    section2 = mo.md("""
    ```python
    def method_two():
        '''Optimized approach'''
        import numpy as np
        return np.arange(10)**2
    ```
    """)

    mo.accordion(
        {
            "Method 1: List Comprehension": section1,
            "Method 2: NumPy": section2,
        }
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## mo.Html + mo.md Combinations

    The following cells test interactions between `mo.Html` and `mo.md`.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.Html nested inside mo.md
    html_component = mo.Html("""
    <div style="border: 2px solid #3b82f6; padding: 16px; border-radius: 8px;">
        <h4 style="margin: 0 0 8px 0; color: #3b82f6;">Custom Component</h4>
        <p style="margin: 0;">This is an <code>mo.Html</code> component.</p>
    </div>
    """)

    mo.md(f"""
    ### mo.Html Inside mo.md

    Here's an HTML component embedded in markdown:

    {html_component}

    Text continues after the HTML component.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.md nested inside mo.Html
    markdown_content = mo.md("""
    ```python
    def example():
        return "Hello from nested markdown!"
    ```
    """)

    mo.Html(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 12px; color: white;">
        <h3 style="margin: 0 0 12px 0;">mo.md Inside mo.Html</h3>
        <div style="background: rgba(255,255,255,0.1); padding: 12px; border-radius: 8px;">
            {markdown_content}
        </div>
    </div>
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Multiple mo.Html components inside mo.md
    badge1 = mo.Html(
        '<span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">Success</span>'
    )
    badge2 = mo.Html(
        '<span style="background: #ef4444; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">Error</span>'
    )
    badge3 = mo.Html(
        '<span style="background: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">Warning</span>'
    )

    mo.md(f"""
    ### Multiple mo.Html Badges in Markdown

    Status indicators: {badge1} {badge2} {badge3}

    These inline HTML components should render correctly within the markdown flow.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.Html with script-like content (should be escaped/safe)
    safe_html = mo.Html("""
    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; overflow-x: auto;">
    &lt;script&gt;
    // This should be displayed as text, not executed
    console.log("Hello");
    &lt;/script&gt;
    </pre>
    """)

    mo.md(f"""
    ### Escaped HTML Content

    HTML entities should be preserved:

    {safe_html}
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Deeply nested: mo.md -> mo.Html -> mo.md
    innermost_md = mo.md("""
    ```bash
    echo "Innermost markdown"
    ```
    """)

    middle_html = mo.Html(f"""
    <div style="border-left: 4px solid #8b5cf6; padding-left: 16px; margin: 12px 0;">
        <em>HTML wrapper around:</em>
        {innermost_md}
    </div>
    """)

    mo.md(f"""
    ### Triple Nesting: md -> Html -> md

    Outer markdown containing:

    {middle_html}

    The code block went through: mo.md → mo.Html → mo.md
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.Html table with mo.md cells
    cell1 = mo.md("**Bold text**")
    cell2 = mo.md("`inline code`")
    cell3 = mo.md("*italic*")
    cell4 = mo.md("```\ncode block\n```")

    mo.Html(f"""
    <table style="border-collapse: collapse; width: 100%;">
        <tr>
            <td style="border: 1px solid #ddd; padding: 12px;">{cell1}</td>
            <td style="border: 1px solid #ddd; padding: 12px;">{cell2}</td>
        </tr>
        <tr>
            <td style="border: 1px solid #ddd; padding: 12px;">{cell3}</td>
            <td style="border: 1px solid #ddd; padding: 12px;">{cell4}</td>
        </tr>
    </table>
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.Html SVG with mo.md
    svg_icon = mo.Html("""
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2L2 7l10 5 10-5-10-5z"/>
        <path d="M2 17l10 5 10-5"/>
        <path d="M2 12l10 5 10-5"/>
    </svg>
    """)

    mo.md(f"""
    ### SVG Inside Markdown

    Icon: {svg_icon} This is a layers icon rendered from inline SVG.

    SVG elements should render correctly when embedded via mo.Html.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Combining mo.Html, mo.md, and mo.hstack/mo.vstack
    code_example = mo.md("""
    ```python
    result = process(data)
    ```
    """)

    description = mo.Html("""
    <div style="padding: 8px; background: #fef3c7; border-radius: 4px;">
        <strong>Note:</strong> This function may raise ValueError
    </div>
    """)

    mo.vstack(
        [
            mo.md("### Combined Layout Example"),
            mo.hstack([code_example, description], justify="start", gap=2),
            mo.md("The code and warning are laid out horizontally above."),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.as_html with mo.md
    plain_text = "This is plain text converted to HTML"
    converted = mo.as_html(plain_text)

    nested_converted = mo.md(f"""
    ### mo.as_html with mo.md

    Converted text: {converted}

    The `mo.as_html()` result should integrate seamlessly.
    """)
    return (nested_converted,)


@app.cell(hide_code=True)
def _(mo, nested_converted):
    # Display the nested_converted from previous cell
    mo.md(f"""
    ### Using Output from Previous Cell

    {nested_converted}

    This tests cross-cell nesting behavior.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Edge case: Empty mo.Html
    empty_html = mo.Html("")

    mo.md(f"""
    ### Empty mo.Html

    Before: |{empty_html}| After

    Empty HTML should not break the layout.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Edge case: mo.Html with only whitespace
    whitespace_html = mo.Html("   \n\t  \n   ")

    mo.md(f"""
    ### Whitespace-Only mo.Html

    Before: [{whitespace_html}] After

    Whitespace HTML should be handled gracefully.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Additional Edge Cases

    The following cells test additional edge cases from #6464 and #7931.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Edge case: Empty mo.md
    empty_md = mo.md("")

    mo.md(f"""
    ### Empty mo.md

    Before: |{empty_md}| After

    Empty markdown should not break the layout.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Verify text formatting renders as HTML, not raw markdown
    formatted_text = mo.md("**bold** and *italic* and `code`")

    mo.md(f"""
    ### Text Formatting Verification

    The following should render as formatted HTML (not raw markdown):

    {formatted_text}

    You should see bold, italic, and inline code - not asterisks/backticks.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # mo.md vs mo.Html __format__ behavior comparison
    md_obj = mo.md("""
    ```
    line1
    line2
    ```
    """)

    html_obj = mo.Html("""<div>
    line1
    line2
    </div>""")

    mo.md(f"""
    ### Format Behavior Comparison

    **mo.md preserves structure** (code block with newlines):

    {md_obj}

    **mo.Html flattens content** (single line):

    {html_obj}

    Notice how mo.md keeps the code block intact while mo.Html flattens to one line.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Nested Wrapper Span Issue

    The following cells highlight the nested wrapper span issue that occurs when
    nesting `mo.md()` calls via f-strings. Each `mo.md()` wraps content in a
    `<span class="markdown prose dark:prose-invert contents">` element, leading
    to redundant nested wrappers.

    See discussion in #6464, #7931.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Simple nested mo.md() - demonstrates redundant wrapper spans
    _inner = mo.md("**bold**")
    _outer = mo.md(f"Text: {_inner}")

    # This creates HTML like:
    # <span class="markdown prose dark:prose-invert contents">
    #   <span class="paragraph">Nested mo.md:
    #     <span class="markdown prose dark:prose-invert contents">
    #       <span class="paragraph">Text:
    #         <span class="markdown prose dark:prose-invert contents">
    #           <span class="paragraph"><strong>bold</strong></span>
    #         </span>
    #       </span>
    #     </span>
    #   </span>
    # </span>
    mo.md(f"Nested mo.md: {_outer}")


@app.cell(hide_code=True)
def _(mo):
    # Two levels of nesting with simple text
    level1 = mo.md("*italic text*")
    level2 = mo.md(f"Level 2: {level1}")
    level3 = mo.md(f"Level 3: {level2}")

    mo.md(f"""
    ### Three Levels of Nested Simple Text

    {level3}

    Each level adds another wrapper span, creating deeply nested HTML.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Nested mo.md with inline elements - shows wrapper span accumulation
    badge = mo.md("`status: ok`")
    message = mo.md(f"Server responded with {badge}")
    full_status = mo.md(f"**Status Update:** {message}")

    mo.md(f"""
    ### Inline Nesting Pattern

    {full_status}

    Common pattern: building up complex inline content from smaller pieces.
    The HTML structure becomes deeply nested even for simple inline content.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Show the actual HTML structure
    inner_md = mo.md("**bold**")

    mo.md(f"""
    ### Inspecting the HTML Output

    The inner markdown's text property:

    ```html
    {inner_md.text}
    ```

    When used via f-string `__format__`, the entire HTML including the
    wrapper span is embedded, creating nested `<span class="markdown ...">` elements.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Comparison: mo.Html vs mo.md nesting behavior
    html_inner = mo.Html("<strong>bold via Html</strong>")
    md_inner = mo.md("**bold via md**")

    mo.md(f"""
    ### Comparing mo.Html vs mo.md Nesting

    **Using mo.Html (no extra wrapper):**

    Inline: {html_inner}

    **Using mo.md (adds wrapper span):**

    Inline: {md_inner}

    Notice: mo.Html embeds cleanly, mo.md adds its own styling wrapper.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Multiple nested items in a row
    item1 = mo.md("**A**")
    item2 = mo.md("**B**")
    item3 = mo.md("**C**")

    mo.md(f"""
    ### Multiple Nested Items Inline

    Items: {item1} | {item2} | {item3}

    Each item carries its own wrapper span, even for single characters.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Nested mo.md in a list context
    list_item1 = mo.md("First item with `code`")
    list_item2 = mo.md("Second item with **bold**")
    list_item3 = mo.md("Third item with *italic*")

    mo.md(f"""
    ### Nested mo.md in List Items

    - {list_item1}
    - {list_item2}
    - {list_item3}

    Each list item has its own markdown wrapper, which may affect spacing.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Workaround: using mo.Html for inline content
    # This avoids the extra wrapper span
    inline_bold = mo.Html("<strong>bold</strong>")
    inline_code = mo.Html("<code>code</code>")

    mo.md(f"""
    ### Workaround: Use mo.Html for Inline Content

    Using mo.Html directly: {inline_bold} and {inline_code}

    This avoids the extra wrapper spans from mo.md, but requires
    writing raw HTML instead of markdown syntax.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    # Edge case: deeply nested with mixed content types
    deep1 = mo.md("core")
    deep2 = mo.Html(f"<em>{deep1}</em>")
    deep3 = mo.md(f"wrapped: {deep2}")
    deep4 = mo.Html(f"<div style='padding: 4px; background: #f0f0f0;'>{deep3}</div>")
    deep5 = mo.md(f"**Final:** {deep4}")

    mo.md(f"""
    ### Deeply Nested Mixed Content (5 levels)

    {deep5}

    Path: md -> Html -> md -> Html -> md

    Each mo.md adds a wrapper span; mo.Html does not.
    """)
    return


@app.cell
def _():
    import marimo as mo
    return (mo,)


if __name__ == "__main__":
    app.run()
