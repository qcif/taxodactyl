# Delete the extra 200 rows at the end of the .fasta file
from Bio import SeqIO
import sys
import os


script_dir = os.path.dirname(__file__)
fasta_path = os.path.join(script_dir,
                          "test-data",
                          "350_taxodactyl_trial.fasta")
REMOVE_N = 200
records = list(SeqIO.parse(fasta_path, "fasta"))
total = len(records)

if total == 0:
    print("Error: No sequences found in FASTA.")
    sys.exit(1)

if REMOVE_N >= total:
    print(f"Error: FASTA only has {total} sequences, "
          f"cannot remove {REMOVE_N}.")
    sys.exit(1)
kept = records[:-REMOVE_N]

SeqIO.write(kept, fasta_path, "fasta")
print(f"Done. Trimmed from {total} → {len(kept)} sequences.")
print(f"Updated file saved: {fasta_path}")
