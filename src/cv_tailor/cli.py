import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from google import genai
from pydantic import ValidationError

from cv_tailor.delivery.base import DeliveryChannel
from cv_tailor.delivery.local_files import LocalFilesChannel
from cv_tailor.delivery.telegram import TelegramChannel
from cv_tailor.errors import ConfigurationError, describe_validation_error
from cv_tailor.models.job import load_jobs
from cv_tailor.models.master_cv import MasterCv, load_master_cv
from cv_tailor.pipeline import Pipeline, exit_code
from cv_tailor.settings import DeliveryMode, Settings
from cv_tailor.tailoring.gemini_tailor import GeminiTailor

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cv_tailor")
    parser.add_argument("--jobs-file", type=Path, default=None)
    parser.add_argument("--delivery", choices=["local", "telegram", "both"], default=None)
    return parser


def load_settings(delivery: DeliveryMode | None) -> Settings:
    try:
        return Settings() if delivery is None else Settings(delivery=delivery)
    except ValidationError as error:
        raise ConfigurationError(describe_validation_error("settings", error)) from None


def build_channels(settings: Settings) -> list[DeliveryChannel]:
    channels: list[DeliveryChannel] = []
    if settings.delivers_to_local:
        channels.append(LocalFilesChannel(settings.output_dir))
    credentials = settings.telegram_credentials
    if settings.delivers_to_telegram and credentials is not None:
        channels.append(TelegramChannel(*credentials))
    return channels


def build_ai(settings: Settings, master: MasterCv) -> GeminiTailor:
    return GeminiTailor(
        client=genai.Client(api_key=settings.gemini_api_key.get_secret_value()),
        master=master,
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        timeout_seconds=settings.gemini_timeout_seconds,
        max_projects=settings.max_projects,
    )


def run(args: argparse.Namespace) -> int:
    settings = load_settings(args.delivery)
    master_json = settings.master_cv_json.get_secret_value() if settings.master_cv_json else None
    jobs_json = settings.jobs_json.get_secret_value() if settings.jobs_json else None
    master = load_master_cv(master_json, settings.master_cv_path)
    jobs = load_jobs(jobs_json, args.jobs_file, settings.max_description_chars)
    pipeline = Pipeline(
        master=master,
        ai=build_ai(settings, master),
        channels=build_channels(settings),
        batch_size=settings.batch_size,
        max_projects=settings.max_projects,
        guard_retry_limit=settings.guard_retry_limit,
    )
    return exit_code(pipeline.run(jobs))


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ConfigurationError as error:
        logger.error("%s", error)
        return 1
