# Xiaoyuzhou Export + SQLite User Manual

## 1) Folder paths

- Project: `/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export`
- Downloads: `/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/downloads`
- Database: `/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/xiaoyuzhou.db`

## 2) Scripts

- Login (save auth): `login.py`
- Download 2 export files: `export.py`
- Import xlsx to SQLite: `import_to_sqlite.py`
- Cron pipeline: `scripts/run_pipeline.sh`

## 3) First-time setup (or when login expires)

```bash
cd /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export
python3 login.py
```

Then log in manually in browser, return terminal, press Enter.

## 4) Manual run (2 steps)

### Step A: Download xlsx files

```bash
cd /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export
python3 export.py
```

Check files:

```bash
ls -lt /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/downloads | head
```

### Step B: Import to SQLite (optional, separate step)

```bash
cd /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export
python3 import_to_sqlite.py
```

Import logic:

- `episode_total`: snapshot model (append records by `snapshot_time + title`)
- `incremental_daily`: upsert by `stat_date`
- For `episode_total`, different snapshots are all kept for trend/history analysis

## 5) Open SQLite and inspect data

```bash
sqlite3 /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/xiaoyuzhou.db
```

Inside sqlite:

```sql
.tables
.schema episode_total
.schema incremental_daily
.mode table
.headers on
```

Exit:

```sql
.quit
```

## 6) Common queries

### Row counts

```sql
SELECT COUNT(*) AS episode_rows FROM episode_total;
SELECT COUNT(*) AS incremental_rows FROM incremental_daily;
```

### Date range (incremental table)

```sql
SELECT MIN(stat_date) AS min_date, MAX(stat_date) AS max_date
FROM incremental_daily;
```

### Query episode by `id` (fast)

```sql
SELECT id, title, publish_date, plays, completion_rate
FROM episode_total
WHERE id = 1;
```

### Latest snapshot top episodes by plays

```sql
SELECT id, title, publish_date, plays
FROM episode_total
WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM episode_total)
ORDER BY plays DESC
LIMIT 10;
```

### Episode performance change over time (by title)

```sql
SELECT snapshot_time, title, plays, completion_rate, comments, shares, favorites, likes
FROM episode_total
WHERE title = 'Your Episode Title'
ORDER BY snapshot_time;
```

### Compare two snapshots for same episode

```sql
SELECT title, snapshot_time, plays, completion_rate
FROM episode_total
WHERE title = 'Your Episode Title'
  AND snapshot_time IN ('2026-03-06 22:20:34', '2026-03-06 23:02:03')
ORDER BY snapshot_time;
```

### Latest 30 days incremental trend

```sql
SELECT stat_date, plays, subscriptions, comments, shares, favorites, likes
FROM incremental_daily
ORDER BY stat_date DESC
LIMIT 30;
```

## 7) Cron (already configured)

Current schedule:

```bash
crontab -l
```

Expected line:

```text
30 21 * * * /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/scripts/run_pipeline.sh
```

## 8) Logs and failure checks

List recent logs:

```bash
ls -lt /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/logs | head
```

Last failure marker:

```bash
cat /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/logs/last_failure.txt
```

Last success marker:

```bash
cat /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/logs/last_success.txt
```

## 9) One-command manual pipeline run

```bash
/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/scripts/run_pipeline.sh
```
