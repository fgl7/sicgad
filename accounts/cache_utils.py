from django.core.cache import cache


def admin_flags_cache_key(user_id: int) -> str:
    return f"accounts:admin_flags:v3:user:{user_id}"


def invalidate_admin_flags_cache(user_id: int) -> None:
    if not user_id:
        return
    cache.delete(admin_flags_cache_key(int(user_id)))
