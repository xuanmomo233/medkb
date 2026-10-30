from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MEDKB_", extra="ignore")

    database_url: str
    invite_code: SecretStr = SecretStr("")
    glm_api_key: SecretStr = SecretStr("")
    glm_models: str = "glm-4.7-flash,glm-4.5-air"
    glm_vision_models: str = "glm-5.3-flash"

    token_ttl_days: int = 90
    img_dir: str = "/data/img"
    textbook_img_dir: str = "/data/textbooks"
    textbook_pdf_dir: str = "/data/textbook-pdfs"
    upload_dir: str = "/data/uimg"
    img_cache_dir: str = "/data/imgcache"
    web_dist_dir: str = "/app/web"

    @property
    def glm_model_list(self) -> list[str]:
        return [m.strip() for m in self.glm_models.split(",") if m.strip()]

    @property
    def glm_vision_model_list(self) -> list[str]:
        return [m.strip() for m in self.glm_vision_models.split(",") if m.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
