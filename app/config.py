from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str
    GEMINI_API_KEY: str
    SECRET_KEY: str
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_EMAIL: str = "mailto:admin@financeapp.com"
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.ALLOWED_ORIGINS.split(",")
            if origin.strip()
        ]

    class Config:
        env_file = ".env"

settings = Settings()
