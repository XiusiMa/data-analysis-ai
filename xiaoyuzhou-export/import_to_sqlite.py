from pathlib import Path
from datetime import datetime
from zipfile import ZipFile
import sqlite3
import xml.etree.ElementTree as ET
import re

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DB_PATH = BASE_DIR / "xiaoyuzhou.db"


def normalize_date(v):
    v = (v or "").strip()
    if re.fullmatch(r"\d{8}", v):
        return f"{v[0:4]}-{v[4:6]}-{v[6:8]}"
    return v


def to_int(v):
    v = (v or "").strip()
    if not v:
        return 0
    try:
        return int(float(v))
    except ValueError:
        return 0


def to_float(v):
    v = (v or "").strip()
    if not v:
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


def parse_xlsx_rows(path):
    ns = {
        "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "p": "http://schemas.openxmlformats.org/package/2006/relationships",
    }

    with ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                text = "".join(t.text or "" for t in si.findall(".//a:t", ns))
                shared.append(text)

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("p:Relationship", ns)
        }

        first_sheet = wb.find("a:sheets/a:sheet", ns)
        if first_sheet is None:
            return []

        rid = first_sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        target = rel_map.get(rid, "")
        if not target:
            return []

        sheet_xml = "xl/" + target if not target.startswith("xl/") else target
        ws = ET.fromstring(zf.read(sheet_xml))

        rows = []
        for row in ws.findall("a:sheetData/a:row", ns):
            values = []
            for c in row.findall("a:c", ns):
                t = c.attrib.get("t")
                v = c.find("a:v", ns)
                val = ""
                if v is not None and v.text is not None:
                    raw = v.text
                    if t == "s":
                        val = shared[int(raw)] if raw.isdigit() else raw
                    else:
                        val = raw
                else:
                    inline = c.find("a:is", ns)
                    if inline is not None:
                        val = "".join(tn.text or "" for tn in inline.findall(".//a:t", ns))
                values.append(val)
            rows.append(values)

        return rows


def ensure_db(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS episode_total (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_time TEXT NOT NULL,
            title TEXT NOT NULL,
            publish_date TEXT,
            plays INTEGER,
            completion_rate REAL,
            comments INTEGER,
            shares INTEGER,
            favorites INTEGER,
            likes INTEGER,
            source_file TEXT,
            imported_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS incremental_daily (
            stat_date TEXT PRIMARY KEY,
            plays INTEGER,
            subscriptions INTEGER,
            comments INTEGER,
            shares INTEGER,
            favorites INTEGER,
            likes INTEGER,
            source_file TEXT,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    migrate_episode_total_schema(conn)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_total_snapshot_title ON episode_total(snapshot_time, title)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_episode_total_title ON episode_total(title)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_episode_total_snapshot_time ON episode_total(snapshot_time)"
    )
    conn.commit()


def migrate_episode_total_schema(conn):
    cols = conn.execute("PRAGMA table_info(episode_total)").fetchall()
    col_names = [c[1] for c in cols]

    if "snapshot_time" in col_names and "imported_at" in col_names:
        return

    conn.execute(
        """
        CREATE TABLE episode_total_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_time TEXT NOT NULL,
            title TEXT NOT NULL,
            publish_date TEXT,
            plays INTEGER,
            completion_rate REAL,
            comments INTEGER,
            shares INTEGER,
            favorites INTEGER,
            likes INTEGER,
            source_file TEXT,
            imported_at TEXT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO episode_total_new (
            snapshot_time, title, publish_date, plays, completion_rate, comments, shares, favorites, likes, source_file, imported_at
        )
        SELECT
            COALESCE(updated_at, datetime('now')),
            title, publish_date, plays, completion_rate, comments, shares, favorites, likes, source_file,
            COALESCE(updated_at, datetime('now'))
        FROM episode_total
        """
    )
    conn.execute("DROP TABLE episode_total")
    conn.execute("ALTER TABLE episode_total_new RENAME TO episode_total")
    conn.commit()


def snapshot_time_from_file(path):
    m = re.match(r"^(\d{8})_(\d{6})_export_\d+_", path.name)
    if m:
        d, t = m.group(1), m.group(2)
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]} {t[0:2]}:{t[2:4]}:{t[4:6]}"
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")


def import_episode_total(conn, rows, source_name, snapshot_time):
    if not rows:
        return 0

    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    required = ["标题", "发布日期", "播放量", "完播率", "评论量", "分享量", "收藏量", "点赞量"]
    if not all(k in idx for k in required):
        return 0

    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for row in rows[1:]:
        if not row:
            continue
        title = row[idx["标题"]].strip() if idx["标题"] < len(row) else ""
        if not title:
            continue

        conn.execute(
            """
            INSERT INTO episode_total (
                snapshot_time, title, publish_date, plays, completion_rate, comments, shares, favorites, likes, source_file, imported_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(snapshot_time, title) DO UPDATE SET
                publish_date=excluded.publish_date,
                plays=excluded.plays,
                completion_rate=excluded.completion_rate,
                comments=excluded.comments,
                shares=excluded.shares,
                favorites=excluded.favorites,
                likes=excluded.likes,
                source_file=excluded.source_file,
                imported_at=excluded.imported_at
            """,
            (
                snapshot_time,
                title,
                normalize_date(row[idx["发布日期"]] if idx["发布日期"] < len(row) else ""),
                to_int(row[idx["播放量"]] if idx["播放量"] < len(row) else ""),
                to_float(row[idx["完播率"]] if idx["完播率"] < len(row) else ""),
                to_int(row[idx["评论量"]] if idx["评论量"] < len(row) else ""),
                to_int(row[idx["分享量"]] if idx["分享量"] < len(row) else ""),
                to_int(row[idx["收藏量"]] if idx["收藏量"] < len(row) else ""),
                to_int(row[idx["点赞量"]] if idx["点赞量"] < len(row) else ""),
                source_name,
                now,
            ),
        )
        count += 1

    conn.commit()
    return count


def import_incremental_daily(conn, rows, source_name):
    if not rows:
        return 0

    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    required = ["日期", "播放", "订阅", "评论", "分享", "收藏", "点赞"]
    if not all(k in idx for k in required):
        return 0

    now = datetime.now().isoformat(timespec="seconds")
    count = 0
    for row in rows[1:]:
        if not row:
            continue
        stat_date = normalize_date(row[idx["日期"]] if idx["日期"] < len(row) else "")
        if not stat_date:
            continue

        conn.execute(
            """
            INSERT INTO incremental_daily (
                stat_date, plays, subscriptions, comments, shares, favorites, likes, source_file, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stat_date) DO UPDATE SET
                plays=excluded.plays,
                subscriptions=excluded.subscriptions,
                comments=excluded.comments,
                shares=excluded.shares,
                favorites=excluded.favorites,
                likes=excluded.likes,
                source_file=excluded.source_file,
                updated_at=excluded.updated_at
            """,
            (
                stat_date,
                to_int(row[idx["播放"]] if idx["播放"] < len(row) else ""),
                to_int(row[idx["订阅"]] if idx["订阅"] < len(row) else ""),
                to_int(row[idx["评论"]] if idx["评论"] < len(row) else ""),
                to_int(row[idx["分享"]] if idx["分享"] < len(row) else ""),
                to_int(row[idx["收藏"]] if idx["收藏"] < len(row) else ""),
                to_int(row[idx["点赞"]] if idx["点赞"] < len(row) else ""),
                source_name,
                now,
            ),
        )
        count += 1

    conn.commit()
    return count


def list_xlsx_files():
    files = list(DOWNLOAD_DIR.glob("*.xlsx"))
    files.sort(key=lambda p: p.stat().st_mtime)
    return files


def main():
    files = list_xlsx_files()
    if not files:
        print(f"未找到 xlsx 文件: {DOWNLOAD_DIR}")
        return

    conn = sqlite3.connect(DB_PATH)
    ensure_db(conn)

    ep_count = 0
    inc_count = 0
    ep_files = 0
    inc_files = 0

    try:
        for f in files:
            rows = parse_xlsx_rows(f)
            name = f.name
            if "单集数据总表" in name:
                snapshot_time = snapshot_time_from_file(f)
                ep_count += import_episode_total(conn, rows, name, snapshot_time)
                ep_files += 1
            elif "增量数据表" in name:
                inc_count += import_incremental_daily(conn, rows, name)
                inc_files += 1
    finally:
        conn.close()

    print(f"数据库: {DB_PATH}")
    print(f"处理文件: 单集数据总表 {ep_files} 个, 增量数据表 {inc_files} 个")
    print(f"upsert 行数: 单集数据总表 {ep_count}, 增量数据表 {inc_count}")


if __name__ == "__main__":
    main()
