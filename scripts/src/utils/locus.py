"""Define a gene locus for the given sample."""

# Fields that are specified for ambiguous synonyms in GenBank queries:
GENBANK_RESTRICTED_FIELDS = [
    'Title',
    'GENE',
]


class Locus:
    """A locus defined in loci.json, or NA if not defined.

    Each locus has a name and a set of synonyms. A string locus can be matched
    against the name with `x in locus` or against the synonyms with
    `locus in x`. The name is always lowercased and stripped of whitespace.
    """

    def __init__(self, name: str, data: dict):
        self.name = name.lower().strip()
        self.printed_name = name.strip()
        self.data = data
        self.ambiguous_synonyms = data.get('ambiguous_synonyms', [])
        self.non_ambiguous_synonyms = data.get('non_ambiguous_synonyms', [])
        self.synonyms = self.ambiguous_synonyms + self.non_ambiguous_synonyms

    def __str__(self):
        return self.printed_name

    def __repr__(self):
        return self.printed_name

    def __bool__(self):
        """Return True if the locus has a name."""
        return self.name != 'na'

    def __eq__(self, value):
        return value.strip().lower() == self.name

    def __contains__(self, synonym: str) -> bool:
        return synonym.lower().strip() in self.synonyms

    @property
    def genbank_query_str(self) -> str:
        """Return a GenBank query string for this locus."""
        query = ' OR '.join(
            f'({synonym}[{field}])'
            for synonym in self.ambiguous_synonyms
            for field in GENBANK_RESTRICTED_FIELDS
        )
        if self.non_ambiguous_synonyms:
            query += ' OR '
            query += ' OR '.join(
                f'({synonym})'
                for synonym in self.non_ambiguous_synonyms
            )
        return query

    def rename(self, name: str) -> 'Locus':
        return Locus(name, self.data.copy())
