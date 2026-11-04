import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
if os.environ.get("VERCEL") and (
    not os.environ.get("SECRET_KEY") or os.environ.get("DEBUG", "").lower() == "true"
):
    raise RuntimeError("Configure SECRET_KEY e DEBUG=false no deploy.")
app = application = get_wsgi_application()
