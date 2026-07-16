from apps.news.models import HomepageSettings


def homepage_settings(request):
    try:
        return {'homepage_settings': HomepageSettings.get_solo()}
    except Exception:
        return {'homepage_settings': None}
