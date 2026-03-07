# 小宇宙导出与入库（简版）

## 路径

- 项目：`/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export`
- 下载目录：`/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/downloads`
- 数据库：`/Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/xiaoyuzhou.db`

## 常用脚本

- 登录并保存状态：`login.py`
- 下载两张表：`export.py`
- 导入 SQLite：`import_to_sqlite.py`
- 一键流水线：`scripts/run_pipeline.sh`

## 手动执行（推荐）

1. 下载 xlsx

```bash
cd /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export
python3 export.py
```

2. 导入 SQLite

```bash
cd /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export
python3 import_to_sqlite.py
```

## 登录失效时

```bash
cd /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export
python3 login.py
```

浏览器手动登录后，回终端按回车。

## 查看数据库

```bash
sqlite3 /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/xiaoyuzhou.db
```

进入后：

```sql
.tables
.mode table
.headers on
SELECT COUNT(*) FROM episode_total;
SELECT COUNT(*) FROM incremental_daily;
```

退出：

```sql
.quit
```

## 常用查询

按 `id` 查单集（快）：

```sql
SELECT id, title, publish_date, plays
FROM episode_total
WHERE id = 1;
```

最新快照下，单集播放量 Top10：

```sql
SELECT id, title, plays
FROM episode_total
WHERE snapshot_time = (SELECT MAX(snapshot_time) FROM episode_total)
ORDER BY plays DESC
LIMIT 10;
```

查看某一单集随时间变化：

```sql
SELECT snapshot_time, title, plays, completion_rate, comments, shares, favorites, likes
FROM episode_total
WHERE title = '你的单集标题'
ORDER BY snapshot_time;
```

查看当前有哪些快照时间：

```sql
SELECT snapshot_time, COUNT(*) AS cnt
FROM episode_total
GROUP BY snapshot_time
ORDER BY snapshot_time DESC;
```

增量数据日期范围：

```sql
SELECT MIN(stat_date), MAX(stat_date)
FROM incremental_daily;
```

## 定时任务与日志

查看 cron：

```bash
crontab -l
```

查看日志：

```bash
ls -lt /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/logs | head
```

失败记录：

```bash
cat /Users/sophia/dev/data-analysis-ai/xiaoyuzhou-export/logs/last_failure.txt
```
