"""Define outcomes from the analysis."""


class DetectedTaxon:
    """A taxon of interest that was detected in the analysis."""
    def __init__(self, toi, rank, taxon, species, accession, identity):
        self.toi = toi
        self.rank = rank
        self.taxon = taxon
        self.species = species
        self.accession = accession
        self.identity = identity

    def to_json(self):
        """Return the object as a JSON-serializable dictionary."""
        return {
            'toi': self.toi,
            'rank': self.rank,
            'taxon': self.taxon,
            'species': self.species,
            'accession': self.accession,
            'identity': self.identity,
        }
