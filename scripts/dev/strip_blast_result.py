"""Read in a BLAST result XML file and split it into individual queries."""

import argparse
import xml.etree.ElementTree as ET

from src.utils import existing_path


def main():
    args = _parse_args()
    n_iterations = args.input_file.read_text().count('</Iteration>')
    for i in range(n_iterations):
        tree = ET.parse(args.input_file)
        root = tree.getroot()
        parent_map = {
            child: parent
            for parent in tree.iter()
            for child in parent
        }
        iterations = list(root.findall('.//Iteration'))
        for idx, elem in enumerate(iterations):
            if idx != i:
                parent_map[elem].remove(elem)
        path = f'blast_result_{i + 1}.xml'
        print(f'Writing file {path}...')
        tree.write(
            path,
            encoding='utf-8',
            xml_declaration=True)


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'input_file',
        type=existing_path,
        help='Path to the input BLAST result XML file.')
    return parser.parse_args()


if __name__ == '__main__':
    main()
