#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert YDEA data for Pleiades
"""

from hashlib import new
from airtight.cli import configure_commandline
from copy import copy
import encoded_csv
import json
import logging
from pprint import pformat, pprint
import re
from shapely.geometry import shape, mapping, polygon
from shapely.validation import explain_validity
import sys

logger = logging.getLogger(__name__)

read_keys = dict()
read_key_options = {
    "accuracy": [
        "Positional accuracy assessment info",
        "accuracy_document",
        "Other notes",
    ],
    "aliases": ["Alias", "Aen"],
    "description": ["Description", "Den"],
    "dissolution": ["P576 dissolved/demolished", "dissolved/demolished"],
    "geom": ["Coordinate location GEOJSON", "P625 coordinate location"],
    "inception": ["Inception", "P571 inception"],
    "place_type": ["Place type", "Place Type", "place_type"],
    "source": ["Source", "source"],
    "title": ["Title", "title", "Len"],
    "location": ["Location", "P361 Part of Dura-Europos"],
    "part_of": [
        "Part of (larger organizational unit at D-E)",
        "P361 Part of (larger organizational unit at D-E)",
    ],
    "succeeds": ["Structure replaces", "P1398 structure replaces"],
}
missing_connection_fields = []
fault_tolerant = None

DEFAULT_LOG_LEVEL = logging.WARNING
OPTIONAL_ARGUMENTS = [
    [
        "-l",
        "--loglevel",
        "NOTSET",
        "desired logging level ("
        + "case-insensitive string: DEBUG, INFO, WARNING, or ERROR",
        False,
    ],
    ["-v", "--verbose", False, "verbose output (logging level == INFO)", False],
    [
        "-w",
        "--veryverbose",
        False,
        "very verbose output (logging level == DEBUG)",
        False,
    ],
    ["-t", "--fault_tolerant", False, "throw fewer exceptions", False],
]
POSITIONAL_ARGUMENTS = [
    # each row is a list with 3 elements: name, type, help
    ["infile", str, "path to input csv file"],
    ["outfile", str, "path to output json file"],
]
PLACE_TYPES = {
    "tower (wall)": "tower-wall",
    "city gate": "city-gate",
    "city block": "city-block",
    "building": "building",
    "complex": "architecturalcomplex",
    "building (house?)": "building",
    "house": "townhouse",
    "synagogue": "synagogue",
    "Q16748868 city walls": "city-wall",
    "q16748868 city walls": "city-wall",
    "q79007 street": "street",
    "q20034791 defensive tower": "tower-defensive",
    "q82117 city gate": "city-gate",
    "q187909 agora": "agora",
    "q1468524 city center": "city-center",
    "q88291 citadel": "citadel",
    "q57346 defensive wall": "defensive-wall",
    "q53060 gate": "gateway",
    "q28228887 insula": "city-block",
    "q1348006 city block": "city-block",
    "q42948 wall": "wall-2",
    "q23418 postern": "postern",
    "q12277 arch": "arch",
    "military assembly ground? training ground?": "space-uncovered",
    "military base": "military-base",
    "temple": "temple-2",
    "townhouse": "townhouse",
    "church": "church-2",
    "siege-ramp": "siege-ramp",
    "siege-mine": "siege-mine",
    "barracks": "barracks",
    "bath": "bath",
    "platform": "platform",
    "sanctuary": "sanctuary",
}
RX_BCE = re.compile(r"(\d+)(\-\d+)? BCE")
RX_CE = re.compile(r"(\d+)(\-\d+)? CE")
CENTURY_TERMS = {
    "-9": "ninth-bce",
    "-8": "eighth-bce",
    "-7": "seventh-bce",
    "-6": "sixth-bce",
    "-5": "fifth-bce",
    "-4": "fourth-bce",
    "-3": "third-bce",
    "-2": "second-bce",
    "-1": "first-bce",
    "1": "first-ce",
    "2": "second-ce",
    "3": "third-ce",
    "4": "fourth-ce",
    "5": "fifth-ce",
    "6": "sixth-ce",
    "7": "seventh-ce",
    "8": "eighth-ce",
    "9": "ninth-ce",
}
RX_REFS = [
    re.compile(r"([A-Za-z ]+ \d{4})"),
    re.compile(r"([A-Za-z ]+ \d{4}),? (p\. \d+)"),
    re.compile(r"([A-Za-z ]+ \d{4}),? (pp?\. \d+-\d+)"),
    re.compile(r"([A-Za-z ]+ \d{4}),? (p\. [xiv]+)"),
    re.compile(r"([A-Za-z ]+ \d{4}),? (pp?\. \d+\-\d+, \d+)"),
    re.compile(r"([A-Za-z ]+ \d{4}),? (Appendix)\.?"),
    re.compile(
        r"J\. A\. (Baird\. 2018)\. Dura-Europos\. " r"(pp?\. ([\d\-]+|\d+, \d+)) \(.+\)"
    ),
    re.compile(r"^(Gelin et al\. \(1997\))"),
    re.compile(
        r"(James, Simon\. 2019)\. The Roman Military Base at Dura-Europos, "
        r"Syria: An Archaeological Visualisation. New York, NY: Oxford "
        r"University Press. (P.66, 230-232)"
    ),
]
REFERENCES = {
    "Baird 2012": {
        "formatted_citation": (
            "Baird, J. A. “The Inner Lives of Ancient Houses: An Archaeology "
            "of Dura-Europos.” In Everyday Life in Roman Dura-Europos: "
            "Household Activities. Oxford University Press, 2012."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/JT7TZ582",
        "access_uri": "https://doi.org/10.1093/acprof:osobl/9780199687657.003.0004",
        "identifier": "978-0-19-180482-3",
    },
    "Baird 2018": {
        "formatted_citation": "Baird, Jennifer A. Dura-Europos. London: Bloomsbury, 2018.",
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/QL32DCUE",
        "access_uri": "http://www.worldcat.org/oclc/1034731631",
        "identifier": "978-1-4725-2365-5; 978-1-4725-2673-1",
    },
    "Cumont 1926": {
        "formatted_citation": (
            "Cumont, Franz. Fouilles de Doura-Europos (1922-1923). Bibliothèque "
            "archéologique et historique 9. Paris: P. Geuthner, 1926."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/WYGADTF8",
        "access_uri": "http://www.worldcat.org/oclc/846262",
    },
    "James 2011": {
        "formatted_citation": (
            "James, Simon. “Stratagems, Combat, and ‘Chemical Warfare’ in the Siege Mines "
            "of Dura-Europos.” American Journal of Archaeology 115, no. 1 (2011): 69–101. "
            "https://doi.org/10.3764/aja.115.1.0069."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/HE28YUIP",
        "access_uri": "https://www.jstor.org/stable/10.3764/aja.115.1.0069",
        "identifier": "10.3764/aja.115.1.0069; 0002-9114",
    },
    "James 2019": {
        "citation_detail": "",
        "formatted_citation": (
            "James, Simon. The Roman Military Base at Dura-Europos, Syria: "
            "An Archaeological Visualization. Oxford, New York: Oxford "
            "University Press, 2019."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/UM57GCTF",
        "access_uri": "http://www.worldcat.org/oclc/1084757192",
        "identifier": "978-0-19-874356-9",
    },
    "Rostovtzeff 1936": {
        "formatted_citation": (
            "Rostovtzeff, M.I., Bellinger, L., Hopkins, C., and Welles, "
            "C.B., eds. The Excavations at Dura-Europos,Conducted by "
            "Yale University and the French Academy of Inscriptions "
            "and Letters; Preliminary Report of Sixth Season of Work, "
            "October 1932 – March 1933. New Haven: Yale University Press, "
            "1936."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/UC843X84",
        "access_uri": "http://hdl.handle.net/2027/mdp.39015016894068",
    },
    "Kraeling 1956": {
        "formatted_citation": (
            "Kraeling, Carl Hermann. The Synagogue. The Excavations at "
            "Dura-Europos Final Report, 8 part 1. New Haven: Yale "
            "University Press, 1956."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/RW89HS3Z",
        "access_uri": "http://www.worldcat.org/oclc/491461650",
    },
    "Gelin 1997": {
        "formatted_citation": (),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/67S99C6X",
        "access_uri": "http://www.worldcat.org/oclc/630177122",
    },
    "von Gerkan 1936": {
        "formatted_citation": (
            "von Gerkan, Armin. “The Fortifications.” In The Excavations at "
            "Dura-Europos, Preliminary Report on the Seventh and Eighth "
            "Seasons, 1933-1934 and 1934-1935, edited by Michael I. "
            "Rostovtzeff, Frank E. Brown, and C. Welles, 4-61. New Haven: "
            "Yale University Press, 1936."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/L4MBW9Y5",
        "access_uri": "http://www.worldcat.org/oclc/896191961",
    },
    "Leriche 1986": {
        "formatted_citation": (
            "Leriche, Pierre. Doura-Europos. Études. Vol. 1. Publication "
            "hors-série / Institut français d’archéologie du Proche-Orient 16. "
            "Paris: P. Geuthner, 1986."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/5TB75YJB",
        "access_uri": "http://www.worldcat.org/oclc/466092686",
        "identifier": "978-2-7053-0356-3",
    },
    "Peppard 2016": {
        "formatted_citation": (
            "Peppard, Michael. The World’s Oldest Church: Bible, Art, and Ritual "
            "at Dura-Europos, Syria. Synkrisis. New Haven: Yale University Press, "
            "2016."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/9XXNNKFI",
        "access_uri": "http://www.worldcat.org/oclc/1295968857",
        "identifier": "978-0-300-21651-6",
    },
    "Kraeling 1967": {
        "formatted_citation": (
            "Kraeling, Carl Hermann and Charles Bradford Welles. The Excavations "
            "at Dura-Europos Final Report VIII. Part II. New Haven: Dura-Europos "
            "Publications, 1967."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/IR2MDI33",
        "access_uri": "http://www.worldcat.org/oclc/490392414",
    },
    "James 2007": {
        "formatted_citation": (
            "James, Simon. “New Light on the Roman Military Base at Dura-Europos: "
            "Interim Report on a Pilot Season of Fieldwork in 2005.” In The Late "
            "Roman Army in the near East from Diocletian to the Arab Conquest : "
            "Proceedings of a Colloquium Held at Potenza, Acerenza and Matera, "
            "Italy / May 2005, edited by A. S. Lewin and P. Pellegrini, 29–47. BAR, "
            "International Series 1717. Oxford: Archaeopress, 2007."
        ),
        "bibliographic_uri": "https://www.zotero.org/groups/2533/items/32ATHVXS",
        "access_uri": "http://www.worldcat.org/oclc/470640847",
        "identifier": "978-1-4073-0161-7",
    },
}
CONNECTION_TARGETS = {
    "Dura-Europos": "https://pleiades.stoa.org/places/893990",
    "city wall": "https://pleiades.stoa.org/places/15685985",
    "City Wall of Dura-Europos": "https://pleiades.stoa.org/places/15685985",
    "City walls of Dura-Europos": "https://pleiades.stoa.org/places/15685985",
    "Part of Military camp after c. 100 CE": "Military Base",
    "citadel of Dura-Europos": "Citadel of Dura-Europos",
    "citadel fortification of Dura-Europos": "Citadel Fortification of Dura-Europos",
    "military campus after c. 100 CE": "Military Campus",
    "agora": "Agora of Dura-Europos",
    "military camp": "Military Base",
}


def titleize(val: str):
    # oh the pain
    t = val.title()
    uncap = [
        "of",
        "10th",
        "2nd",
        "3rd",
        "4th",
        "5th",
        "6th",
        "7th",
        "8th",
        "9th",
        "at",
        "and",
        "in",
    ]
    uncapd = {u.title(): u for u in uncap}
    words = t.split()
    new_words = []
    for word in words:
        try:
            new_words.append(uncapd[word])
        except KeyError:
            new_words.append(word)
    t = " ".join(new_words)
    return t


def read_ydea(fn: str):
    r = encoded_csv.get_csv(fn, sample_lines=2000)

    new_fieldnames = []
    for fn in r["fieldnames"]:
        if fn != fn.strip():
            new_fn = fn.strip()
            for row in r["content"]:
                row[new_fn] = row[fn]
                row.pop(fn)
            new_fieldnames.append(new_fn)
        else:
            new_fieldnames.append(fn)
    r["fieldnames"] = new_fieldnames
    fieldnames_set = set(new_fieldnames)

    # figure out which variant column title this file uses
    global read_keys
    global read_key_options

    for read_k, options in read_key_options.items():
        try:
            read_keys[read_k] = determine_field_key_variant(fieldnames_set, options)
        except RuntimeError:
            raise RuntimeError(
                f"Cannot find key variant for {read_k} (options: {options}) in {fieldnames_set}."
            )
    logger.debug(f"read_keys: {pformat(read_keys, indent=4)}")

    return r["content"]


def determine_field_key_variant(fieldnames=set, options: list = []):
    for k in options:
        if k in fieldnames:
            return k
    raise RuntimeError()


def build_description(feature):
    k = read_keys["description"]
    orig_desc = feature[k].strip()
    desc = orig_desc.split()
    desc = desc[0][0].capitalize() + desc[0][1:] + " " + " ".join(desc[1:])
    if desc[-1] != ".":
        desc += "."
    if orig_desc != desc:
        logger.debug(f'Description changed: "{desc}" from "{orig_desc}"')
    k = read_keys["inception"]
    start = feature[k].strip()
    k = read_keys["dissolution"]
    end = feature[k].strip()
    if (
        start == "c. 150 BCE"
        and end == "256 CE"
        and feature[place_type_key] in ["tower (wall)", "city gate"]
    ):
        desc += (
            "  Built ca. 150 BCE, the city's fortifications were breached "
            "in 256 CE and went out of use thereafter."
        )
    return desc


def build_names(feature):
    k = read_keys["aliases"]
    aliases = feature[k].strip()
    for delim in [";", ","]:
        if delim in aliases:
            aliases = [a.strip() for a in aliases.split(delim)]
            break
    if isinstance(aliases, str):
        aliases = [aliases]
    names = []
    for alias in aliases:
        name = {
            "nameLanguage": "en",
            "nameTransliterated": alias,
            "nameAttested": alias,
            "nameType": "geographic",
            "attestations": [
                {"timePeriod": "twentieth-ce", "confidence": "confident"},
                {"timePeriod": "twenty-first-ce", "confidence": "confident"},
            ],
        }
        names.append(name)
    return names


def parse_year(raw: str):
    m = RX_BCE.search(raw)
    if m is None:
        m = RX_CE.search(raw)
        if m is None:
            if raw == "3rd century":
                cooked = 300
            elif raw == "after late second c. CE":
                cooked = 300
            else:
                raise ValueError('could not parse year from string "{}"'.format(raw))
        else:
            cooked = int(m.group(1))
    else:
        cooked = -1 * int(m.group(1))
    # print('parse_year: {}'.format(cooked))
    return cooked


def build_attestations(feature):
    start = feature[read_keys["inception"]].strip()
    end = feature[read_keys["dissolution"]].strip()
    attestations = []
    if start != "" and end != "":
        start = parse_year(start)
        end = parse_year(end)
        start_century = -(-start // 100)
        end_century = -(-end // 100)
        if start_century == end_century:
            attestations.append(
                {
                    "timePeriod": CENTURY_TERMS[str(start_century)],
                    "confidence": "confident",
                }
            )
        else:
            for i in range(start_century, end_century):
                if i == 0:
                    continue  # out, vile astronomers!
                attestations.append(
                    {"timePeriod": CENTURY_TERMS[str(i)], "confidence": "confident"}
                )
    elif start != "":
        start = parse_year(start)
        start_century = -(-start // 100)
        attestations.append(
            {"timePeriod": CENTURY_TERMS[str(start_century)], "confidence": "confident"}
        )
    elif end != "":
        end = parse_year(end)
        end_century = -(-end // 100)
        attestations.append(
            {"timePeriod": CENTURY_TERMS[str(end_century)], "confidence": "confident"}
        )
    return attestations


def build_location_title(feature):
    accuracy_key = read_keys["accuracy"]
    accuracy_datum = feature[accuracy_key].strip()
    accuracy_datum = " ".join(accuracy_datum.split())
    if accuracy_datum == "dura-europos-block-l7-chen":
        title = "Total station location of"
    elif accuracy_datum in [
        "dura-europos-walls-and-towers-baird-chen",
        "dura-europos-james-chen",
    ]:
        title = "Plan location of"
    elif accuracy_datum.startswith(
        "Features related to the streets and blocks of Dura-Europos "
        "were prepared by Anne Chen in 2021 on the basis of Baird "
        "2012 Fig. 1.3."
    ):
        title = "Plan location of"
    elif accuracy_datum.startswith(
        "plan used= James 2019 Plate XXII, georectified plan in QGIS"
    ):
        title = "Plan location of"
    elif accuracy_datum.startswith(
        "Features related to the walls and towers of Dura-Europos "
        "were prepared by Anne Chen in 2020 on the basis of Baird "
        "2012 Fig. 1.3"
    ):
        title = "Plan location of"
    elif accuracy_datum.startswith(
        "coordinates based on Baird 2008 totalstation data supplemented by georeferenced version of James 2019"
    ):
        title = "Plan location of"
    elif "y713":
        title = "Total Station and Photogrammetric Location of"
    else:
        raise RuntimeError(f'Unexpected accuracy value: "{feature[accuracy_key]}"')
    return " ".join((title, feature[read_keys["title"]]))


def build_remains(feature):
    if "traces" in feature[read_keys["description"]]:
        return "traces"
    else:
        return "substantive"


def build_locations(feature):
    locations = []
    k = read_keys["title"]
    t_text = titleize(feature[k].strip())
    k = read_keys["geom"]
    g_text = feature[k].strip()
    if g_text == "":
        g_data = list()
        logger.warning(f'Skipping empty geometry for "{t_text}".')
    else:
        try:
            g_data = json.loads(g_text)
        except json.decoder.JSONDecodeError as err:
            logger.error(
                f'Skipping malformed geometry for "{t_text}". Got JSONDecodeError: {str(err)}'
            )
            g_data = []
        else:
            if isinstance(g_data, dict):
                g_data = [
                    g_data,
                ]
            elif not isinstance(g_data, list):
                raise NotImplementedError(
                    f"Expected {list} or {dict}. Got {type(g_data)}."
                )
    # logger.info(f'Processing {len(g_data)} geometries in {t_text}.')
    for g_obj in g_data:
        s = shape(g_obj)
        if s.geom_type not in ["Point", "Polygon", "LineString"]:
            logger.error(
                f'Unsupported geometry type "{s.geom_type}" for "{t_text}". Skipping ...'
            )
            continue
        if s.geom_type == "Polygon":
            s = polygon.orient(s)
        if not s.is_valid:
            s = s.buffer(0)
        if s.is_valid:
            accuracy_key = read_keys["accuracy"]
            accuracy_datum = feature[accuracy_key].strip()
            accuracy_datum = " ".join(accuracy_datum.split())

            if accuracy_datum in [
                "dura-europos-block-l7-chen",
                "dura-europos-walls-and-towers-baird-chen",
                "dura-europos-james-chen",
            ]:
                accuracy_id = feature[accuracy_key]
            else:
                accuracy_id = "ydea-chen-nominal-5m"
            # else:
            #     msg = f"Unexpected accuracy value ({accuracy_datum}) for feature with title={feature[read_keys['title']]}"
            #     if fault_tolerant:
            #         logger.error(msg)
            #     else:
            #         raise RuntimeError(msg)
            location = {
                "title": build_location_title(feature),
                "geometry": mapping(s),
                "archaeologicalRemains": build_remains(feature),
                "accuracy": "/features/metadata/" + accuracy_id,
                "attestations": build_attestations(feature),
                "featureType": list(
                    set(
                        [
                            PLACE_TYPES[pt.lower().strip()]
                            for pt in feature[read_keys["place_type"]].split(";")
                            if pt.strip() != ""
                        ]
                    )
                ),
            }
            locations.append(location)
        else:
            msg = '{} (title: "{}")'.format(explain_validity(s), t_text)
            if fault_tolerant:
                logger.error(msg)
            else:
                raise ValueError(msg)
    return locations


def parse_connections(target_string, ctype=None):
    connections = []
    targets = [s.strip() for s in target_string.strip().split(";") if s.strip() != ""]
    for target in targets:
        if ctype is None:
            if target.strip() == "":
                continue
            relationship_type = target.split()[0]
            target = " ".join(target.split()[1:])
        else:
            relationship_type = ctype
        try:
            real_target = CONNECTION_TARGETS[target]
        except KeyError:
            try:
                real_target = CONNECTION_TARGETS[titleize(target)]
            except KeyError:
                real_target = target

        connections.append(
            {"connection": real_target, "relationshipType": relationship_type}
        )
    return connections


def build_connections(feature, places={}):
    connections = []
    categories = [
        ("location", "at"),
        ("part_of", "part_of_physical"),
        ("succeeds", "succeeds"),
    ]
    for field_name, connection_type in categories:
        k = read_keys[field_name]
        try:
            feature[k]
        except KeyError:
            global missing_connection_fields
            if k not in missing_connection_fields:
                missing_connection_fields.append(field_name)
                logger.warning(
                    f'Expected connection fieldname "{field_name}" is missing from input data.'
                )

        try:
            connections.extend(parse_connections(feature[k], connection_type))
        except KeyError:
            pass
    if connections:
        logger.debug(connections)
    for connection in connections:
        target_string = connection["connection"].strip()
        if target_string.startswith("https://pleiades.stoa.org/places/"):
            continue
        try:
            places[target_string]
        except KeyError:
            target_string = titleize(target_string)
            try:
                places[target_string]
            except KeyError:
                keys = list(places.keys())
                keys.sort()
                keys = "".join([f"\t{k}\n" for k in keys])
                t = titleize(feature[read_keys["title"]])
                raise RuntimeError(
                    f'Failed connection title match for {t}: "{target_string}".\nAvailable keys:\n{keys}.'
                )
            else:
                connection["connection"] = target_string
    return connections


def build_references(feature):
    references = []
    k = read_keys["source"]
    sources = [s.strip() for s in feature[k].strip().split(";") if s.strip() != ""]
    failures = []
    for source in sources:
        reference = None
        for rx in RX_REFS:
            short_title = ""
            m = rx.fullmatch(source)
            if m is not None:
                short_title = m.group(1)
                removals = ["et al.", ".", "(", ")", ", Simon"]
                for removal in removals:
                    short_title = short_title.replace(removal, "")
                short_title = " ".join(short_title.split()).strip()
                reference = copy(REFERENCES[short_title])
                reference["short_title"] = short_title
                try:
                    citation_detail = m.group(2)
                except IndexError:
                    pass
                else:
                    reference["citation_detail"] = citation_detail
                references.append(reference)
        if reference is None:
            failures.append(source)
    mined_references = mine_references(failures)
    references.extend(mined_references)
    return references


def mine_references(sources: list):
    # are there any references buried in longer discursive text?

    references = []
    for source in sources:
        for rx in RX_REFS:
            for m in rx.finditer(source):
                short_title = m.group(1)
                # print(short_title)
                removals = ["et al.", ".", "(", ")", ", Simon"]
                for removal in removals:
                    short_title = short_title.replace(removal, "")
                short_title = " ".join(short_title.split()).strip()
                reference = copy(REFERENCES[short_title])
                reference["short_title"] = short_title
                try:
                    citation_detail = m.group(2)
                except IndexError:
                    pass
                else:
                    reference["citation_detail"] = citation_detail
                references.append(reference)
    return references


def make_pjson(in_data):
    places = {}
    features_by_title = {}
    for i, feature in enumerate(in_data):
        k = read_keys["title"]
        title = titleize(feature[k].strip())
        try:
            places[title]
        except KeyError:
            features_by_title[title] = feature
        else:
            raise RuntimeError(f'Title collision error with "{title}".')
        place = {
            "title": title,
            "description": build_description(feature),
            "placeType": list(
                set(
                    [
                        PLACE_TYPES[pt.lower().strip()]
                        for pt in feature[read_keys["place_type"]].split(";")
                        if pt.strip() != ""
                    ]
                )
            ),
            "names": build_names(feature),
            "locations": build_locations(feature),
            # 'connections': build_connections(feature),
            "references": build_references(feature),
        }
        places[title] = place

    for title, place in places.items():
        place["connections"] = build_connections(features_by_title[title], places)
    return [place for title, place in places.items()]


def write_pjson(pjson, fn):
    with open(fn, "w", encoding="utf-8") as f:
        json.dump(pjson, f, ensure_ascii=False, indent=4)


def main(**kwargs):
    """
    main function
    """
    # logger = logging.getLogger(sys._getframe().f_code.co_name)

    global fault_tolerant
    logger.debug(kwargs.keys())
    fault_tolerant = kwargs["fault_tolerant"]

    # read CSV
    in_data = read_ydea(kwargs["infile"])

    pjson = make_pjson(in_data)

    write_pjson(pjson, kwargs["outfile"])

    pass


if __name__ == "__main__":
    main(
        **configure_commandline(
            OPTIONAL_ARGUMENTS, POSITIONAL_ARGUMENTS, DEFAULT_LOG_LEVEL
        )
    )
