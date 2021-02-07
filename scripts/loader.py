from __future__ import print_function

from Acquisition import aq_parent
import argparse
import json
from pleiades.dump import getSite, spoofRequest
from Products.Archetypes.exceptions import ReferenceException
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safe_unicode
from Products.PleiadesEntity.content.interfaces import IWork
from Products.validation import validation
import re
import string
import sys
import transaction


RX_SPACE = re.compile(r'[^\w\s]')
RX_UNDERSCORE = re.compile(r'\_')


def make_name_id(name):
    this_id = name.split(',')[0].strip()
    this_id = RX_SPACE.sub('', this_id)
    this_id = RX_UNDERSCORE.sub('-', this_id)
    this_id = this_id.lower().strip()
    this_id = '-'.join(this_id.split())
    while '--' in this_id:
        this_id = this_id.replace('--', '-')
    this_id = this_id.strip('-')
    return safe_unicode(this_id)


def build_names(place_data, plone_context):
    names = []
    for name in place_data['names']:
        new_id = make_name_id(name['nameTransliterated'])
        print('"{}": "{}"'.format(name['nameTransliterated'], new_id))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create new Pleiades places.')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        dest='dry_run', help='No changes will be made.')
    parser.add_argument('--workflow', choices=['publish', 'review', 'draft'],
                        default='draft',
                        help='Direct edit, or set as review or draft.')
    parser.add_argument('--message', default="Editorial adjustment (batch)",
                        help='Commit message.')
    parser.add_argument('--owner', help='Content owner. Defaults to "admin"')
    parser.add_argument('--creators', nargs='*', default=[],
                        help='Creators. Separated by spaces.')
    parser.add_argument('--contributors',  default=[],
                        nargs='*', help='Contributors. Separated by spaces.')
    parser.add_argument('file', type=file, help='Path to JSON import file')
    parser.add_argument('-c', help='Optional Zope configuration file.')
    try:
        args = parser.parse_args()
    except IOError, msg:
        parser.error(str(msg))
    new_places = json.loads(args.file.read())

    app = spoofRequest(app)
    site = getSite(app)

    workflow = getToolByName(site, "portal_workflow")
    membership = getToolByName(site, "portal_membership")

    loaded_ids = []
    done = 0
    print('Loading {} new places '.format(len(new_places)))
    sys.stdout.flush()
    for place in new_places:
        content_type = 'Place'
        path = 'places'
        content = site.restrictedTraverse(path.encode('utf-8'))
        new_id = content.generateId(prefix='')
        loaded_ids.append(new_id)
        content.invokeFactory(content_type, new_id)
        content = content[new_id]
        for k, v in place.items():
            if k in ['locations', 'names']:
                continue  # address these after the place is created
            
            if k == 'references':
                key = 'referenceCitations'
            else:
                key = k
            field = content.getField(key)
            if field is None:
                raise RuntimeError(
                    'content.getField() returned None for field '
                    '"{}"'.format(k))

            if k == 'title':
                content.setTitle(v)
            elif k == 'description':
                content.setDescription(v)
            elif k == 'references':
                field.resize(len(v), content)
                content.setReferenceCitations(v)
            else:
                try:
                    field.set(content, v)
                except ReferenceException:
                    print(
                        'Invalid reference on field "{}". Skipping.'.format(k))

        if len(place['names']) > 0:
            build_names(place, content)

        # locations tbd

        done += 1
        if done % 10 == 0:
            print('.', end='')
            sys.stdout.flush()

    if args.dry_run:
        # abandon everything we've done, leaving the ZODB unchanged
        transaction.abort()
        print('\nDry run. No changes made in Plone.')
    else:
        print()
        path_base = 'places/'
        for new_id in loaded_ids:
            path = path_base + new_id
            content = site.restrictedTraverse(path.encode('utf-8'))
            content.reindexObject()
            content.reindexObject(idxs=['modified'])
        # make all the changes to the database
        transaction.commit()
        print('Place creation and reindexing complete:')
    for new_id in loaded_ids:
        path = path_base + new_id
        content = site.restrictedTraverse(path.encode('utf-8'))
        print('"{}", "{}"'.format(
            new_id, content.Title()
        ))




