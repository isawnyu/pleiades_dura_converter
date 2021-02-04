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
import shapely

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


def read_ydea(fn: str):
    r = encoded_csv.get_csv(fn)
    return r['content']


def make_pjson(in_data):
    places = []
    for i, feature in enumerate(in_data):
        place = {
            'title': feature['Title'],
            'description': feature['Description'],
            'placeType': PLACE_TYPES[feature['Place type']]
        }
        places.append(place)
    return places


def write_pjson(pjson, fn):
    with open(fn, 'w', encoding='utf-8') as f:
        json.dump(pjson, f)


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
