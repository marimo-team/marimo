import pypandoc


# Convert markdown docstrings to RST.
#
# LaTeX written with single or double $ is supported, but not with \[ \],
# as per Pandoc Markdown syntax.
def md2rst(app, what, name, obj, options, lines):
    del app, what, name, obj, options
    md = "\n".join(lines)
    rst = pypandoc.convert_text(md, "rst", format="md")
    lines.clear()
    lines += rst.splitlines()
