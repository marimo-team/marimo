# Migration Plan: Sphinx to MkDocs Material

## ✅ COMPLETED

1. Created required directories:

   ```bash
   mkdir -p docs/{assets,stylesheets,overrides}
   
2. Started theme customization:
   - Created `docs/stylesheets/extra.css` with initial styles
3. Created overrides directory:
   - Set up `docs/overrides/main.html` with custom template
4. Started content migration:
   - Created new `index.md` with modern features
   - Created initial API reference with mkdocstrings integration
5. Skipped versioning

## TODO

## 1. Setup and Structure

1. Move assets:
   - Copy favicon and logo to `docs/assets/`

## 2. Content Migration

1. Update Markdown syntax:

   - Replace Sphinx directives with Material MkDocs equivalents:
     - `.. note::` → `!!! note`
     - `.. warning::` → `!!! warning`
     - `.. code-block::` → ````python`
     - `:ref:` → Regular Markdown links
   - Update cross-references to use MkDocs style
   - Convert any sphinx-specific extensions to MkDocs alternatives

2. Navigation:
   - Review and update nav structure in mkdocs.yml
   - Ensure all pages are properly linked
   - Create index.md files for sections

## 3. Features Migration

1. Search:

   - MkDocs Material search is enabled by default
   - No additional configuration needed

2. Extensions:
   - Replace Sphinx extensions with MkDocs equivalents:
     - sphinx-copybutton → Built-in copy button
     - sphinx-sitemap → Built-in sitemap
     - myst_parser → Native Markdown support

## 4. Theme Customization

1. Colors and Branding:

   - Update color scheme in mkdocs.yml

2. Navigation:
   - Configure navigation features in mkdocs.yml
   - Set up tabs and sections as needed

## 5. Testing and Deployment

1. Local Testing:

   ```bash
   hatch run docs:serve
   
2. Build Test:

   ```bash
   hatch run docs:build
   
## 6. Cleanup

1. Remove old Sphinx files:

   - conf.py
   - make.bat
   - Old RST files
   - Sphinx-specific directories

2. Update CI/CD:
   - Update documentation build scripts
   - Update deployment workflows

## 7. Post-Migration

1. Verify:

   - All pages render correctly
   - Search functionality works
   - Navigation is intuitive
   - Code blocks are properly highlighted
   - API documentation is complete

2. SEO:

   - Update meta descriptions
   - Verify sitemap generation
   - Check social cards

3. Documentation:
   - Update contributing guidelines
   - Document new documentation workflow
