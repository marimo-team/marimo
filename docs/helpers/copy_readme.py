from docutils.parsers.rst import Directive
import re
import os
from myst_parser.docutils_ import Parser


class ReadmePartDirective(Directive):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = False

    def run(self):
        header = self.arguments[0]

        # Read and parse the README.md file
        current_dir = os.path.dirname(os.path.realpath(__file__))
        readme = os.path.join(current_dir, "..", "..", "README.md")
        with open(readme, "r") as file:
            content = file.read()

        # Find the header
        header_pattern = r"#{1,6} " + re.escape(header)
        match = re.search(header_pattern, content, re.IGNORECASE)
        if not match:
            return []
        level = match.group(0).count("#")
        next_header_with_same_level = r"\n#{" + str(level) + r"} "
        next_match = re.search(
            next_header_with_same_level, content[match.end() :], re.IGNORECASE
        )

        stripped_content = ""
        if match:
            # Extract everything below the header, up to the next header
            if next_match and next_match.group(0):
                stripped_content = content[
                    match.end() : match.end() + next_match.start()
                ].strip()
            else:
                stripped_content = content[match.end() :].strip()

        # Update asset links, add a leading slash if needed
        stripped_content = re.sub(
            r"https.*?docs/_static", "/_static", stripped_content
        )
        Parser().parse(stripped_content, self.state.document)
        return []
