import argparse
from common import pydicombatch

def parse_arguments():
    parser = argparse.ArgumentParser(description='PYDICOM Batch Processing Tool')
    parser.add_argument(
        '-c', '--config',
        default='config/dicom-template.yml',
        help='Path to config file (default: config/dicom-template.yml)'
    )
    parser.add_argument(
        '-o', '--operation',
        choices=['c-find', 'c-move'],
        default='c-find',
        help='Operation to perform (default: c-find)'
    )
    return parser.parse_args()

print("\n█▀█ █▄█ █▀▄ █ █▀▀ █▀█ █▀▄▀█   █▄▄ ▄▀█ ▀█▀ █▀▀ █░█\n█▀▀ ░█░ █▄▀ █ █▄▄ █▄█ █░▀░█   █▄█ █▀█ ░█░ █▄▄ █▀█\n")

def main():
    args = parse_arguments()
    pydicombatch(args.config, args.operation.lower())

if __name__ == "__main__":
    main()
