from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name: str = "我的FastAPI项目"
    port: int = 8000
    debug: bool = False

    model_config = SettingsConfigDict(env_file=".env")
settings = Settings()