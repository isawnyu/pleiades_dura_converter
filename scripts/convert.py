#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert YDEA data for Pleiades
"""

from airtight.cli import configure_commandline
import encoded_csv
import json
import logging
from pprint import pprint
import re
from shapely.geometry import shape, mapping, polygon
from shapely.validation import explain_validity
import sys

logger = logging.getLogger(__name__)

DEFAULT_LOG_LEVEL = logging.WARNING
OPTIONAL_ARGUMENTS = [
    ['-l', '--loglevel', 'NOTSET',
        'desired logging level (' +
        'case-insensitive string: DEBUG, INFO, WARNING, or ERROR',
        False],
    ['-v', '--verbose', False, 'verbose output (logging level == INFO)',
        False],
    ['-w', '--veryverbose', False,
        'very verbose output (logging level == DEBUG)', False],
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ['infile', str, 'path to input csv file'],
    ['outfile', str, 'path to output json file']
]
PLACE_TYPES = {
    'tower (wall)': 'tower-wall',
    'city gate': 'city-gate'
}
RX_BCE = re.compile(r'(\d+) BCE')
RX_CE = re.compile(r'(\d+) CE')
CENTURY_TERMS = {
    '-9': 'ninth-bce',
    '-8': 'eighth-bce',
    '-7': 'seventh-bce',
    '-6': 'sixth-bce',
    '-5': 'fifth-bce',
    '-4': 'fourth-bce',
    '-3': 'third-bce',
    '-2': 'second-bce',
    '-1': 'first-bce',
    '1': 'first-ce',
    '2': 'second-ce',
    '3': 'third-ce',
    '4': 'fourth-ce',
    '5': 'fifth-ce',
    '6': 'sixth-ce',
    '7': 'seventh-ce',
    '8': 'eighth-ce',
    '9': 'ninth-ce'
}
RX_REFS = [
    re.compile(r'^([A-Za-z ]+ \d{4})$'),
    re.compile(r'^([A-Za-z ]+ \d{4}),? (p\. \d+)$'),
    re.compile(r'^([A-Za-z ]+ \d{4}),? (pp?\. \d+\-\d+)$'),
]
REFERENCES = {
    'Baird 2012': {
        'formatted_citation': (
            'Baird, J. A. “The Inner Lives of Ancient Houses: An Archaeology '
            'of Dura-Europos.” In Everyday Life in Roman Dura-Europos: '
            'Household Activities. Oxford University Press, 2012.'),
        'bibliographic_uri':
            'https://www.zotero.org/groups/2533/items/JT7TZ582',
        'access_uri':
            'https://doi.org/10.1093/acprof:osobl/9780199687657.003.0004',
        'identifier': '978-0-19-180482-3'
    },
    'Baird 2018': {
        'formatted_citation':
            'Baird, Jennifer A. Dura-Europos. London: Bloomsbury, 2018.',
        'bibliographic_uri':
            'https://www.zotero.org/groups/2533/items/QL32DCUE',
        'access_uri': 'http://www.worldcat.org/oclc/1034731631',
        'identifier': '978-1-4725-2365-5; 978-1-4725-2673-1'
    },
    'James 2019': {
        'citation_detail': '',
        'formatted_citation': (
            'James, Simon. The Roman Military Base at Dura-Europos, Syria: '
            'An Archaeological Visualization. Oxford, New York: Oxford '
            'University Press, 2019.'),
        'bibliographic_uri':
            'https://www.zotero.org/groups/2533/items/UM57GCTF',
        'access_uri': 'http://www.worldcat.org/oclc/1084757192',
        'identifier': '978-0-19-874356-9'
    }
}


def read_ydea(fn: str):
    r = encoded_csv.get_csv(fn)
    return r['content']


def build_description(feature):
    desc = feature['Description'].strip()
    desc = desc.split()
    desc = desc[0].capitalize() + ' ' + ' '.join(desc[1:])
    if desc[-1] != '.':
        desc += '.'
    start = feature['Inception'].strip()
    end = feature['Dissolved/demolished'].strip()
    if start == 'c. 150 BCE' and end == '256 CE':
        desc += (
            '  Built ca. 150 BCE, the city\'s fortifications were breached '
            'in 256 CE and went out of use thereafter.')
    return desc


def build_names(feature):
    alias = feature['Alias'].strip()
    names = []
    if alias != '':
        name = {
            'nameLanguage': 'en',
            'nameTransliterated': alias,
            'nameAttested': alias,
            'nameType': 'geographic',
            'attestations': [
                {
                    'timePeriod': 'twentieth-ce',
                    'confidence': 'confident'
                },
                {
                    'timePeriod': 'twenty-first-ce',
                    'confidence': 'confident'
                }
            ]
        }
        names.append(name)
    return names


def parse_year(raw: str):
    m = RX_BCE.search(raw)
    if m is None:
        m = RX_CE.search(raw)
        if m is None:
            raise ValueError(
                'could not parse year from string "{}"'.format(raw))
        cooked = int(m.group(1))
    else:
        cooked = -1 * int(m.group(1))
    return cooked


def build_attestations(feature):
    start = feature['Inception'].strip()
    end = feature['Dissolved/demolished'].strip()
    attestations = []
    if start != '' and end != '':
        start = parse_year(start)
        end = parse_year(end)
        print('start: {}'.format(start))
        print('end: {}'.format(end))
        start_century = -(-start // 100)
        end_century = -(-end // 100)
        for i in range(start_century, end_century):
            if i == 0:
                continue  # out, vile astronomers!
            attestations.append(
                {
                    'timePeriod': CENTURY_TERMS[str(i)],
                    'confidence': 'confident'
                })
    return attestations


def build_location_title(feature):
    if feature['accuracy_document'] == 'dura-europos-block-l7-chen':
        title = "Total station location of"
    elif feature['accuracy_document'] == (
        'dura-europos-walls-and-towers-baird-chen'
    ):
        title = "Plan location of"
    return ' '.join((title, feature['Title']))


def build_locations(feature):
    locations = []
    g = feature['Coordinate location GEOJSON'].strip()
    print(g)
    if g.startswith('{ "type": '):
        s = shape(json.loads(g))
        if s.geom_type == 'Polygon':
            s = polygon.orient(s)
        if s.is_valid:
            location = {
                'title': build_location_title(feature),
                'geometry': mapping(s),
                'archaeologicalRemains': 'substantive',
                'accuracy':
                    '/features/metadata/' + feature['accuracy_document'],
                'attestations': build_attestations(feature),
                'featureType': PLACE_TYPES[feature['Place type'].strip()]
            }
            locations.append(location)
        else:
            raise ValueError(explain_validity(s))
    return locations


def parse_connections(target_string, ctype=None):
    connections = []
    targets = [s.strip() for s in target_string.strip().split(';')]
    for target in targets:
        if ctype is None:
            relationship_type = target.split()[0]
            target = ' '.join(target.split()[1:])
        else:
            relationship_type = ctype
        connections.append(
            {
                'connection': target,
                'relationshipType': relationship_type
            }
        )
    return connections


def build_connections(feature):
    connections = []
    try:
        connections.extend(
            parse_connections(
                feature['Part of (larger organizational unit at D-E)'],
                'part_of_physical'))
    except KeyError:
        pass
    try:
        connections.extend(
            parse_connections(
                feature['Structure replaces'], 'succeeds'))
    except KeyError:
        pass
    try:
        connections.extend(
            parse_connections(feature['Other connections']))
    except KeyError:
        pass
    return connections


def build_references(feature):
    references = []
    sources = [s.strip() for s in feature['source'].strip().split(';')]
    for source in sources:
        reference = None
        for rx in RX_REFS:
            m = rx.match(source)
            if m is not None:
                short_title = m.group(1)
                reference = REFERENCES[short_title]
                break
        if reference is None:
            raise RuntimeError('failed workid lookup for {}'.format(source))
        reference['short_title'] = short_title
        citation_detail = m.group(2)
        reference['citation_detail'] = citation_detail
        references.append(reference)
    return references


def make_pjson(in_data):
    places = []
    for i, feature in enumerate(in_data):
        place = {
            'title': feature['Title'].strip(),
            'description': build_description(feature),
            'placeType': PLACE_TYPES[feature['Place type'].strip()],
            'names': build_names(feature),
            'locations': build_locations(feature),
            'connections': build_connections(feature),
            'references': build_references(feature)
        }
        
        places.append(place)
    return places


def write_pjson(pjson, fn):
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(pjson, f, ensure_ascii=False, indent=4)


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)

    # read CSV
    in_data = read_ydea(kwargs['infile'])

    pjson = make_pjson(in_data)

    write_pjson(pjson, kwargs['outfile'])

    pass


if __name__ == "__main__":
    main(**configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL))
