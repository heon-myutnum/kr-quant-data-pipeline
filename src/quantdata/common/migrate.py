"""sql/ddl/V*.sql을 순서대로 한 번씩 적용한다. 적용한 파일이 바뀌면 실패한다."""
import hashlib
import os
import pathlib
import re
import sys

import psycopg2

LEDGER = """
CREATE TABLE IF NOT EXISTS public.schema_migration (
    version    integer PRIMARY KEY,
    filename   text NOT NULL,
    sha256     char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now()
)"""
LOCK_KEY = 7461001


def migrate(dsn: str, ddl_dir: str) -> list[str]:
    files = sorted(pathlib.Path(ddl_dir).glob("V*__*.sql"))
    conn = psycopg2.connect(dsn)
    applied_now: list[str] = []
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
            cur.execute(LEDGER)
            cur.execute("SELECT version, sha256 FROM public.schema_migration")
            applied = {v: s.strip() for v, s in cur.fetchall()}
            for f in files:
                m = re.fullmatch(r"V(\d{4})__.+\.sql", f.name)
                if not m:
                    raise SystemExit(f"bad migration name: {f.name}")
                version = int(m.group(1))
                body = f.read_text(encoding="utf-8")
                digest = hashlib.sha256(body.encode()).hexdigest()
                if version in applied:
                    if applied[version] != digest:
                        raise SystemExit(f"{f.name} changed after it was applied")
                    continue
                cur.execute(body)
                cur.execute(
                    "INSERT INTO public.schema_migration (version, filename, sha256)"
                    " VALUES (%s, %s, %s)",
                    (version, f.name, digest),
                )
                applied_now.append(f.name)
    finally:
        conn.close()
    return applied_now


if __name__ == "__main__":
    done = migrate(os.environ["WAREHOUSE_DSN"], sys.argv[1] if len(sys.argv) > 1 else "sql/ddl")
    print("applied:", done or "nothing")
