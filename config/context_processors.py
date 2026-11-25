from django.conf import settings


def app_version(request):
    return {
        "APP_VERSION": settings.APP_VERSION,
        "APP_NAME": settings.APP_NAME,
        "APP_FULL_NAME": settings.APP_FULL_NAME,
        "DEV_BROWSER_AUTO_RELOAD": settings.DEV_BROWSER_AUTO_RELOAD,
    }
