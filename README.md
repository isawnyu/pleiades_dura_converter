# config

python virtual environment

do pip install -U pip then
try just installing with `pip - requirements_dev.txt`, but if there's 5 bazillion shapely errors then you'll need to:

```bash
brew install geos
brew install cython
brew install numpy
pip install shapely --no-binary shapely
pip install -r requirements_dev.txt
```

# running

```bash
python scripts/convert.py -v  ../data/units-blocks-streets-tre-20211102.csv ~/scratch/foo.json
```

# uploading

Use scripts/place_maker.py.

```bash
ssh isaw1
cd /srv/python27-apps/pleiades4/


usage: interpreter [-h] [--dry-run] [--nolist] [--message MESSAGE]
                   [--owner OWNER] [--groups GROUPS] [--creators CREATORS]
                   [--contributors CONTRIBUTORS] [--tags SUBJECTS] [-c C]
                   file

Create new Pleiades places.

positional arguments:
  file                  Path to JSON import file

optional arguments:
  -h, --help            show this help message and exit
  --dry-run             No changes will be made.
  --nolist              Do not output list of places.
  --message MESSAGE     Commit message.
  --owner OWNER         Content owner. Defaults to "admin"
  --groups GROUPS       Group names. Separated by spaces or commas.
  --creators CREATORS   Creators. Separated by spaces or commas.
  --contributors CONTRIBUTORS
                        Contributors. Separated by spaces or commas.
  --tags SUBJECTS       Tags (subjects). Separated by spaces or commas.
  -c C                  Optional Zope configuration file.

