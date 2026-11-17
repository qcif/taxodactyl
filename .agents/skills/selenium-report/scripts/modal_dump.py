"""Dump the visible text of elements in a taxodactyl HTML report.

Usage:
    python3 -I modal_dump.py REPORT.html [ID_PREFIX]

Prints the text of every element whose id starts with ID_PREFIX
(default: 'dbCov'), whitespace collapsed, with <strong> text wrapped in
'**' so flag labels stand out. Script and style contents are skipped.
Standard library only, so it runs with any python3.

Useful prefixes:
    dbCov            DB coverage sections (dbCovTarget/Related/Country-*)
    dbCovTarget-pmi  one section type for one group
    pmi- / toi-      whole PMI/TOI coverage modals (summary tab)
    candidate-       whole candidate coverage modals (candidates tab)
    publicationsModal
"""
import re
import sys
from html.parser import HTMLParser

DEFAULT_PREFIX = 'dbCov'
VOID_TAGS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'source', 'track', 'wbr',
}
SKIP_TAGS = {'script', 'style'}
BLOCK_TAGS = {'p', 'div', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}


class ElementTextDumper(HTMLParser):
    """Collect text for each element whose id starts with a prefix."""

    def __init__(self, prefix: str):
        super().__init__(convert_charrefs=True)
        self.prefix = prefix
        self.stack = []
        self.active = []
        self.done = []
        self.skip = 0

    def _emit(self, text: str):
        for capture in self.active:
            capture[1].append(text)

    def handle_starttag(self, tag, attrs):
        if tag in VOID_TAGS:
            return
        if tag in SKIP_TAGS:
            self.skip += 1
        el_id = dict(attrs).get('id') or ''
        capture = None
        if el_id.startswith(self.prefix):
            capture = [el_id, []]
            self.active.append(capture)
        if tag in BLOCK_TAGS:
            self._emit('\n')
        if tag == 'strong':
            self._emit('**')
        self.stack.append((tag, capture))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        while self.stack:
            open_tag, capture = self.stack.pop()
            if open_tag == 'strong':
                self._emit('**')
            if capture is not None:
                self.active.remove(capture)
                self.done.append(capture)
            if open_tag == tag:
                break

    def handle_data(self, data):
        if not self.skip:
            self._emit(data)


def main():
    path = sys.argv[1]
    prefix = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PREFIX
    with open(path, encoding='utf-8') as f:
        html = f.read()
    dumper = ElementTextDumper(prefix)
    dumper.feed(html)
    for el_id, parts in dumper.done:
        lines = [
            re.sub(r'\s+', ' ', line).strip()
            for line in ''.join(parts).split('\n')
        ]
        print(f'===== #{el_id}')
        for line in lines:
            if line:
                print('   ', line)


if __name__ == '__main__':
    main()
