"""Development server with static assets explicitly disabled from browser cache."""

from django.conf import settings
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.contrib.staticfiles.management.commands.runserver import Command as StaticRunserverCommand


class NoCacheStaticFilesHandler(StaticFilesHandler):
    """Serve local CSS/JS without cache so a browser reload always sees edits."""

    def serve(self, request):
        response = super().serve(request)
        response["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response


class Command(StaticRunserverCommand):
    """Replace Django's development static handler only while DEBUG is enabled."""

    def get_handler(self, *args, **options):
        handler = super().get_handler(*args, **options)
        use_static_handler = options["use_static_handler"]
        insecure_serving = options["insecure_serving"]
        if use_static_handler and (settings.DEBUG or insecure_serving):
            # The parent already constructed a StaticFilesHandler. Reuse its
            # wrapped WSGI application while replacing only the response headers.
            application = handler.application if isinstance(handler, StaticFilesHandler) else handler
            return NoCacheStaticFilesHandler(application)
        return handler
