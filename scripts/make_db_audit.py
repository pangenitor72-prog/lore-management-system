import sqlite3, pathlib, os

# Paths
db_path = pathlib.Path("data/lore.db")
out_path = pathlib.Path("docs/audit/db_schema_full.txt")

# Connect
with sqlite3.connect(db_path) as conn, open(out_path, "w", encoding="utf-8") as f:
    cur = conn.cursor()

    f.write("# Database Schema & Statistics Report\n\n")

    # ---------- TABLES ----------
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    total_rows = 0
    f.write("## Table Inventory\n")
    f.write(f"Total tables: {len(tables)}\n\n")

    for t in tables:
        f.write(f"### Table: {t}\n")

        # Columns
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        for cid, name, coltype, notnull, default, pk in cols:
            flags = []
            if pk: flags.append("PK")
            if notnull: flags.append("NOT NULL")
            meta = f" ({', '.join(flags)})" if flags else ""
            f.write(f"- {name}: {coltype or 'UNKNOWN'}{meta}\n")

        # Row count
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
        except Exception as e:
            count = f"Error: {e}"
        f.write(f"Row count: {count}\n")
        if isinstance(count, int):
            total_rows += count

        # Foreign keys
        cur.execute(f"PRAGMA foreign_key_list({t})")
        fk = cur.fetchall()
        if fk:
            f.write("Foreign Keys:\n")
            for _, seq, table, from_col, to_col, on_update, on_delete, match in fk:
                f.write(f"  → {from_col} → {table}.{to_col} "
                        f"(on update: {on_update}, on delete: {on_delete})\n")

        # Indexes
        cur.execute(f"PRAGMA index_list({t})")
        idx = cur.fetchall()
        if idx:
            f.write("Indexes:\n")
            for _, name, unique, origin, partial in idx:
                f.write(f"  • {name} (unique={bool(unique)}, origin={origin})\n")

        f.write("\n")

    # ---------- DB-LEVEL STATS ----------
    f.write("\n## Database Summary\n")
    f.write(f"Total tables: {len(tables)}\n")
    f.write(f"Total rows: {total_rows}\n")

    # Size on disk
    try:
        size_bytes = os.path.getsize(db_path)
        size_mb = size_bytes / (1024 * 1024)
        f.write(f"Database file size: {size_mb:.2f} MB\n")
    except Exception as e:
        f.write(f"Database size: Error ({e})\n")

print(f"\n✅  Full database audit written to {out_path}")
