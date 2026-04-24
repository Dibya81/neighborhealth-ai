from functools import lru_cache
from supabase import create_client, Client
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_supabase() -> Client:
    """
    Returns a cached Supabase client using the service role key.

    IMPORTANT:
    - Always use the service_role key here (bypasses RLS, safe for backend only)
    - Never expose this client or key to the frontend
    - The @lru_cache ensures we create the client exactly once per process

    Usage anywhere in the app:
        from db.client import get_supabase
        sb = get_supabase()
        result = sb.table("wards").select("*").execute()
    """
    settings = get_settings()
    logger.info("Initialising Supabase client [%s]", settings.supabase_url)

    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    return client
