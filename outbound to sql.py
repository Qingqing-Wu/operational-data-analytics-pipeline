import os
import shutil
import hashlib
from datetime import datetime

import pandas as pd
import pymysql


CATEGORY = "outbound"

# replace with the file the excel located
INPUT_DIR = r"C:\Users"
ARCHIVE_DIR = os.path.join(INPUT_DIR, "_archive")
BAD_DIR = os.path.join(INPUT_DIR, "_bad")

DB = dict(
    host = "XXX",
    port = "XXX",
    user = "root",
    password = "XXXXXXX",
    database="blue_ocean",
    charset="utf8mb4",
    autocommit=False,
)

MAIN_TABLE = "Outbound"
LOG_TABLE = "etl_file_log"


FINAL_COLS = [
    "Stock Out Code", "Create Time", "Client Code", "Order Code", "wayBill Num.", "UPC",
    "product Name", "quantity", "Notes", "Stock Out Type", "Stock Out Time", "Stock Out Person",
    "Confirm Person", "Confirm Time", "SN"
]


# functions
def ensure_dirs():
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.makedirs(BAD_DIR, exist_ok=True)


def md5_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def safe_move(src: str, dst_dir: str):
    base = os.path.basename(src)
    dst = os.path.join(dst_dir, base)
    if os.path.exists(dst):
        name, ext = os.path.splitext(base)
        dst = os.path.join(dst_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
    shutil.move(src, dst)


def read_any_table(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()

    if ext in [".xlsx", ".xls"]:
        return pd.read_excel(path)

    if ext == ".csv":
        for enc in ("utf-8", "utf-8-sig", "cp1252"):
            try:
                return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(path, encoding="utf-8")

    raise ValueError(f"Unsupported file: {path}")


def already_done(conn, category: str, filename: str, file_hash: str) -> bool:
    sql = f"""
        SELECT 1
        FROM `{LOG_TABLE}`
        WHERE category=%s AND filename=%s AND file_hash=%s AND status='SUCCESS'
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (category, filename, file_hash))
        return cur.fetchone() is not None


def write_log(conn, category: str, filename: str, file_hash: str, row_count, status: str, message: str = ""):
    sql = f"""
        INSERT INTO `{LOG_TABLE}`
        (category, filename, file_hash, processed_at, row_count, status, message)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (category, filename, file_hash, datetime.now(), row_count, status, (message or "")[:2000]))
    conn.commit()


def create_main_table_if_not_exists(conn):
    cols_sql = ["`hash_id` CHAR(32) NOT NULL"]
    for c in FINAL_COLS:
        cols_sql.append(f"`{c}` TEXT NULL")

    ddl = f"""
    CREATE TABLE IF NOT EXISTS `{MAIN_TABLE}` (
        {", ".join(cols_sql)},
        PRIMARY KEY (`hash_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    with conn.cursor() as cur:
        cur.execute(ddl)
    conn.commit()


def compute_hash_id(df: pd.DataFrame) -> pd.Series:
    """
    kind of primary key: Stock Out Code + UPC + SN 生成 hash_id。
    """
    def norm(v) -> str:
        if pd.isna(v):
            return ""
        return str(v).strip()

    def make(row):
        key = f"{norm(row.get('Stock Out Code'))}_{norm(row.get('UPC'))}_{norm(row.get('SN'))}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    return df.apply(make, axis=1)


def upsert_mysql(conn, df: pd.DataFrame) -> int:
    cols = ["hash_id"] + FINAL_COLS
    df = df[cols].copy()

    rows = []
    for _, r in df.iterrows():
        out = []
        for x in r.values:
            if pd.isna(x):
                out.append(None)
            else:
                out.append(x if isinstance(x, (int, float)) else str(x))
        rows.append(tuple(out))

    placeholders = ",".join(["%s"] * len(cols))
    col_list = ",".join([f"`{c}`" for c in cols])

    update_list = ",".join([f"`{c}`=VALUES(`{c}`)" for c in FINAL_COLS])

    sql = f"""
        INSERT INTO `{MAIN_TABLE}` ({col_list})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {update_list}
    """

    with conn.cursor() as cur:
        cur.executemany(sql, rows)
    conn.commit()

    return len(rows)


def main():
    ensure_dirs()
    conn = pymysql.connect(**DB)

    create_main_table_if_not_exists(conn)

    files = sorted([
        f for f in os.listdir(INPUT_DIR)
        if f.lower().endswith((".xlsx", ".xls", ".csv"))
        and not f.startswith("_")
    ])

    for filename in files:
        path = os.path.join(INPUT_DIR, filename)
        file_hash = md5_file(path)

        if already_done(conn, CATEGORY, filename, file_hash):
            write_log(conn, CATEGORY, filename, file_hash, row_count=0, status="SKIPPED",
                      message="Same hash already processed.")
            print(f"SKIPPED: {filename}")
            continue

        try:
            df = read_any_table(path)

            df.columns = df.columns.map(lambda x: x.strip() if isinstance(x, str) else x)

            file_month = filename[:6] if filename[:6].isdigit() else "unknown"
            df["file_month"] = f"{file_month[:4]}-{file_month[4:]}" if file_month != "unknown" else "unknown"
            df["source_file"] = filename

            missing = [c for c in FINAL_COLS if c not in df.columns]
            if missing:
                raise ValueError(f"Missing columns: {missing}")

            df = df[FINAL_COLS].copy()

            df["hash_id"] = compute_hash_id(df)

            n = upsert_mysql(conn, df)

            write_log(conn, CATEGORY, filename, file_hash, row_count=len(df),
                      status="SUCCESS", message=f"Upserted rows: {n}")
            print(f"SUCCESS: {filename} rows={len(df)}")

            safe_move(path, ARCHIVE_DIR)

        except Exception as e:
            write_log(conn, CATEGORY, filename, file_hash, row_count=None,
                      status="FAILED", message=str(e))
            print(f"FAILED: {filename} -> {e}")

            try:
                safe_move(path, BAD_DIR)
            except Exception:
                pass

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
