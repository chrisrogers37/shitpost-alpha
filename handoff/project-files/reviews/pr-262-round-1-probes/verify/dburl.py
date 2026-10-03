"""Print a URL on DEV_DATABASE_URL's server for database argv[1], as user argv[2] (password from argv[3] file)."""
import os, sys
from sqlalchemy.engine import make_url
url = make_url(os.environ["DEV_DATABASE_URL"]).set(drivername="postgresql", database=sys.argv[1])
if len(sys.argv) > 2:
    url = url.set(username=sys.argv[2], password=open(sys.argv[3]).read().strip())
print(url.render_as_string(hide_password=False))
