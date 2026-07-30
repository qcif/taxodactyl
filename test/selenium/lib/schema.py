"""Component/field/type schema for the report YAML fixtures.

Assertion types don't vary per report — only values do — so the mapping
lives here in code. Consumed by:
- Report.from_schema() to build empty skeletons for the `testkit ingest` CLI
- Report.to_yaml() to stamp `type:` on each emitted assertion
- collect_all() to know which components exist
"""


SIMPLE_COMPONENTS = {
    "input_sequence_modal": {
        "sample_id": "contains",
        "dna_sequence": "contains",
    },
    "overview_tab": {
        "conclusion_text": "contains",
        "species_found": "list",
        "toi_row_count": "int",
        "toi_green_tick_first_row": "bool",
        "conclusion_flag": "contains",
        "toi_flag": "contains",
        "preliminary_flag": "contains",
        "matching_species_strong": "int",
        "matching_species_moderate": "int",
        "matching_species_weak": "int",
    },
    "candidate_tab": {
        "tab_title": "contains",
        "candidate_flag_text": "contains",
        "strong_alginment_identity": "float",
        "moderate_alginment_identity": "float",
        "weak_alginment_identity": "float",
        "strong_hits": "int",
        "moderate_hits": "int",
        "weak_hits": "int",
        "lowest_hit": "float",
    },
    "candidate_tab_table": {
        "species": "list",
        "no_of_hits": "list",
        "top_identity": "list",
        "median_identity": "list",
        "min_identity": "list",
        "top_e_value": "list",
        "publication": "list",
    },
    "blast_modal": {
        "title": "contains",
        "rank": "int",
        "accession": "contains",
        "subject": "contains",
        "length": "int",
        "identity": "float",
        "bitscore": "float",
        "evalue": "contains",
        "coverage": "float",
        "alignment_text": "bool",
        "char_more_than_10": "bool",
        "domain": "contains",
        "kingdom": "contains",
        "phylum": "contains",
        "class": "contains",
        "order": "contains",
        "family": "contains",
        "genus": "contains",
        "species": "contains",
    },
    "tree_modal": {
        "title": "contains",
        "min_node": "min",
    },
    "toi_tab": {
        "toi_flag_text": "contains",
        "toi_outcome": "contains",
        "toi_reasoning": "contains",
        "toi_number_of_rows": "int",
    },
    "toi_table": {
        "toi_match": "bool",
        "toi": "list",
        "match_rank": "list",
        "match_taxon": "list",
        "match_species": "list",
        "match_accession": "list",
        "match_identity": "list",
    },
}


GROUPED_COMPONENTS = {
    "database_coverage": {
        "groups": ("pmi", "toi", "candidate"),
        "fields": {
            "title": "list",
            "flag_text1": "list",
            "record_count": "list",
            "flag_text2": "list",
            "species_count": "list",
            "species_total": "list",
            "min_bar_count": "min",
            "first_bar_species": "list",
            "first_bar_count": "list",
            "final_text": "list",
        },
    },
    "publication_modal": {
        "groups": ("candidates",),
        "fields": {
            "title": "list",
            "source": "list",
            "count": "list",
        },
    },
}


COMPONENT_ORDER = (
    "input_sequence_modal",
    "overview_tab",
    "candidate_tab",
    "candidate_tab_table",
    "database_coverage",
    "publication_modal",
    "blast_modal",
    "tree_modal",
    "toi_tab",
    "toi_table",
)
