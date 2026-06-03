from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Two ways to configure the database:

    1. Set ``APP_DATABASE_URL`` directly (used in local dev / docker compose).
    2. Set the parts (``DB_HOST``, ``DB_PORT``, ``DB_NAME``, ``DB_USERNAME``,
       ``DB_PASSWORD``) — used in ECS where username/password come from the
       AWS-managed RDS secret as separate env-var injections.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url_override: str | None = Field(default=None, validation_alias="APP_DATABASE_URL")
    db_host: str = Field(default="localhost", validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_name: str = Field(default="ecommerce", validation_alias="DB_NAME")
    db_username: str = Field(default="postgres", validation_alias="DB_USERNAME")
    db_password: str = Field(default="postgres", validation_alias="DB_PASSWORD")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+psycopg://{self.db_username}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
