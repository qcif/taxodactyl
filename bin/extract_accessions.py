#!/usr/bin/env python3

"""
Description:
    Utility script to extract hit accesions from a Taxodactyl pipeline output 
    blast_result.xml file to be used to create subset database. 
    See /docs/subset_blastdb.md

Usage:
    ./extract_accessions.py <path_to_xml> --outdir <destination>

Positional arguments:
	<path_to_xml>    Path the the input blast_result.xml file.
	
Options:
    -o, --outdir  Path where the list of accessions will be saved (default=pwd).
"""

import os
import argparse
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "filepath", 
        help="Path to the blast_result.xml input file."
    )

    parser.add_argument(
        "-o", "--outdir", 
        type=str, 
        default=os.getcwd(), 
        help="Path to location to output subset database. (default: pwd)."
    )

    args = parser.parse_args()

    input_filepath = args.filepath
    input_filename = os.path.splitext(os.path.basename(input_filepath))[0]
    output_filename = f"{input_filename}_accessions"
    output_filepath = os.path.join(args.outdir, output_filename)

    try:
        input_file = open(input_filepath, mode = "r")
        tree = ET.parse(input_file)
        root = tree.getroot()
        print(f"Scanning {input_filepath} for hit accessions.")
        hit_accessions = root.findall(".//Hit_accession")
    except FileNotFoundError:
        print(f"Error: Input file {input_filepath} not found.")
    except Exception as e:
            print(f"Input file error: {input_filepath}, {e}.")
    else:
        try:
            output_file = open(output_filepath, mode = "w")
        except Exception as e:
            print(f"Output file error: {output_filepath}, {e}.")
        else:
            for hit in hit_accessions:
                output_file.write(hit.text+"\n")
            print(f"Writing {len(hit_accessions)} hit accessions to {output_filepath}")
            output_file.close()
        input_file.close()
        print("Finished!")

if __name__ == "__main__":
    main()
