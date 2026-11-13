from dataclasses import dataclass

from psycopg_pool import ConnectionPool

from app.core.settings import settings

database_pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    timeout=2,
    kwargs={"connect_timeout": 2},
    open=False,
)


@dataclass(frozen=True)
class DatabaseHealth:
    connected: bool
    migration_version: str | None = None


def open_database_pool() -> None:
    database_pool.open(wait=False)


def close_database_pool() -> None:
    database_pool.close()


def get_database_health() -> DatabaseHealth:
    try:
        with database_pool.connection(timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    return DatabaseHealth(connected=False)

                cursor.execute(
                    'SELECT migration_name FROM "_prisma_migrations" '
                    "WHERE finished_at IS NOT NULL AND rolled_back_at IS NULL "
                    "ORDER BY finished_at DESC LIMIT 1"
                )
                migration = cursor.fetchone()
                return DatabaseHealth(
                    connected=True,
                    migration_version=migration[0] if migration else None,
                )
    except Exception:
        return DatabaseHealth(connected=False)


def postgres_is_reachable() -> bool:
    return get_database_health().connected
