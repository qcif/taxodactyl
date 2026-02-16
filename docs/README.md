# Rendering the docs

`scripts/dev/render_docs.py` should be run to render ./src/* templates into HTML 
documents for distribution. To edit these docs, always edit the template in src
rather than the output HTML file, or your changes will be lost the next time the
document is rendered.

The templating system allow config values to be rendered dynamically into the docs,
rather than hard-coded. It also allows us to write docs in Markdown and distribute
them on the web in HTML format.

Only the docs found in `./src/` are templated, the others are just hand-written.
