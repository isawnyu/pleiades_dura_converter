from __future__ import print_function

from Acquisition import aq_parent
import argparse
import json
from pleiades.dump import getSite, spoofRequest
from Products.Archetypes.exceptions import ReferenceException
from Products.CMFCore.utils import getToolByName
from Products.PleiadesEntity.content.interfaces import IWork
from Products.validation import validation
import sys
import transaction

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
            if k in ['names', 'locations']:
                continue  # until we figure out how to do this
            
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
                        
        done += 1
        if done % 10 == 0:
            # save RAM by committing a subtransaction to disk
            transaction.get().commit(True)
            print('.', end='')
            sys.stdout.flush()

    if args.dry_run:
        # abandon everything we've done, leaving the ZODB unchanged
        transaction.abort()
        print('\nDry run. No changes made in Plone.')
    else:
        path_base = 'places/'
        done = 0
        for new_id in loaded_ids:
            path = path_base + new_id
            content = site.restrictedTraverse(path.encode('utf-8'))
            content.reindexObject()
            content.reindexObject(idxs=['modified'])
            done += 1
            if done % 10 == 0:
                transaction.get().commit(True)
        # make all the changes to the database
        transaction.commit()
        print('\nPlace creation and reindexing complete:')
        for new_id in loaded_ids:
            path = path_base + new_id
            content = site.restrictedTraverse(path.encode('utf-8'))
            print('"{}", "{}"'.format(
                new_id, content.Title()
            ))




