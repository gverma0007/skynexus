"""Explicit hosting capabilities; local deployments retain their collectors."""
from app.core.config import get_settings


def capabilities():
    free = get_settings().free_demo
    return {'profile': 'free_demo' if free else 'full', 'continuous_collection': not free,
            'queued_reports': not free, 'model_training': not free,
            'historical_replay': True, 'cached_evaluation': True,
            'idle_timeout_seconds': 180 if free else 0}


def restricted(path, method):
    if not get_settings().free_demo:
        return False
    return (path.startswith('/api/report-jobs') or
            (method == 'POST' and path == '/api/experiments') or
            (method == 'POST' and path.startswith('/api/cases/') and path.endswith('/download')))
