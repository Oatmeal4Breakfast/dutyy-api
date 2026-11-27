import sentry_sdk

from src.config import get_sentry_config


def configure_sentry() -> None:
    config = get_sentry_config()

    sentry_sdk.init(
        dsn=config.sentry_dsn,
        enable_logs=True,
        environment=config.env.value,
        release=config.sentry_release,
        traces_sample_rate=config.traces_sample_rate,
    )
