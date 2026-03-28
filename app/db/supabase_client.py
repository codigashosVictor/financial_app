from supabase import create_client, Client
from app.config import settings

def get_supabase(access_token: str = None) -> Client:
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    if access_token:
        client.postgrest.auth(access_token)
    return client

def get_supabase_admin() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)