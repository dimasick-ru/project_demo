from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    db_host: str = "127.0.0.1"
    db_port: int = 5432
    db_name: str = "test_db"
    db_user: str = "test_user"
    db_password: SecretStr

def get_settings() -> Settings:
    return Settings()
