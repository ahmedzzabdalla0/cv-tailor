from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DeliveryMode = Literal["local", "telegram", "both"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
        frozen=True,
    )

    gemini_api_key: SecretStr
    gemini_model: str = Field(min_length=1)
    gemini_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    gemini_timeout_seconds: int = Field(default=120, gt=0)
    batch_size: int = Field(default=3, ge=1)
    max_description_chars: int = Field(default=6000, ge=1)
    max_projects: int = Field(default=3, ge=0)
    guard_retry_limit: int = Field(default=1, ge=0)
    delivery: DeliveryMode = "local"
    output_dir: Path = Path("out")
    master_cv_path: Path = Path("data/master_cv.json")
    master_cv_json: SecretStr | None = None
    jobs_json: SecretStr | None = None
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    @model_validator(mode="after")
    def require_telegram_credentials(self) -> Self:
        if self.delivers_to_telegram and self.telegram_credentials is None:
            raise ValueError(
                "telegram_bot_token and telegram_chat_id are required when delivery "
                "includes telegram"
            )
        return self

    @property
    def delivers_to_local(self) -> bool:
        return self.delivery in ("local", "both")

    @property
    def delivers_to_telegram(self) -> bool:
        return self.delivery in ("telegram", "both")

    @property
    def telegram_credentials(self) -> tuple[str, str] | None:
        if self.telegram_bot_token and self.telegram_chat_id:
            return self.telegram_bot_token.get_secret_value(), self.telegram_chat_id
        return None
