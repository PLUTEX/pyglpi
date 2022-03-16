from . import GLPI
import argparse
import sys
import csv

parser = argparse.ArgumentParser(description='Fetch list of items from GLPI')
parser.add_argument('item_type')
parser.add_argument(
    '--format',
    help='Output format',
    choices=['csv', 'tsv', 'json'],
    default='tsv',
)
parser.add_argument(
    '--columns',
    help='Limit columns to show (comma-separated)',
)

args = parser.parse_args()
if args.columns:
    columns = args.columns.split(',')
else:
    columns = None
glpi_api = GLPI()

out = []
for result in glpi_api(args.item_type).GET(params={'expand_dropdowns': 'true'}).ranges:
    parsed = result.json()
    if not columns:
        columns = parsed[0].keys()
    out.extend([item[col] for col in columns] for item in result.json())

if args.format == 'json':
    import json
    json.dump(out, sys.stdout)
else:
    writer = csv.writer(
        sys.stdout,
        delimiter=',' if args.format == 'csv' else '\t',
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writerow(columns)
    writer.writerows(out)
