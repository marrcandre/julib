import json
import os
from pathlib import Path
from urllib.parse import urlsplit
origin=os.environ['BACKEND_ORIGIN'].rstrip('/')
url=urlsplit(origin)
if url.scheme!='https' or not url.hostname or url.path:raise SystemExit('BACKEND_ORIGIN precisa ser uma origem HTTPS.')
config={'rewrites':[{'source':f'/{prefix}/:path*','destination':origin+f'/{prefix}/:path*'} for prefix in ['api','accounts','admin','static']]+[{'source':'/:path*','destination':'/index.html'}], 'headers':[{'source':'/colecao/:path*','headers':[{'key':'Cache-Control','value':'no-store'},{'key':'X-Robots-Tag','value':'noindex, nofollow'},{'key':'Referrer-Policy','value':'no-referrer'}]}]}
Path('frontend/vercel.json').write_text(json.dumps(config,indent=2)+'\n')
