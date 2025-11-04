#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日更新运动员训练状态
逻辑：
- 从 tb_athlete 获取所有 id（运动员主键）
- 到 tb_activity 中根据 athlete_id 查询最近 42 天、7 天 TSS 平均
- 计算 fitness（42天）、fatigue（7天）、status（两者差）
- 写入 tb_athlete_daily_state 表
"""

import pymysql
from datetime import date, timedelta, datetime

# === 数据库配置 ===
DB_CONFIG = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "86230ce6558fd9a1",
    "database": "ry-system",
    "charset": "utf8mb4"
}

def get_connection():
    """建立数据库连接"""
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)

def get_avg_tss(cursor, athlete_id, days):
    """计算最近 N 天内的平均 TSS，若没有记录则返回 0"""
    now = datetime.now()
    start_time = now - timedelta(days=days)
    cursor.execute("""
        SELECT AVG(COALESCE(tss, 0)) AS avg_tss
        FROM tb_activity
        WHERE athlete_id = %s
          AND start_date BETWEEN %s AND %s
    """, (athlete_id, start_time, now))
    row = cursor.fetchone()
    return float(row["avg_tss"] or 0.0)   # ✅ 转成 float


def update_daily_state():
    conn = get_connection()
    cursor = conn.cursor()
    today = date.today()

    # 获取所有运动员 id
    cursor.execute("SELECT id FROM tb_athlete")
    athlete_ids = [row["id"] for row in cursor.fetchall()]

    total = len(athlete_ids)
    updated = 0

    for athlete_id in athlete_ids:
        # 最近42天健康度（fitness）
        fitness = get_avg_tss(cursor, athlete_id, 42)
        # 最近7天疲劳度（fatigue）
        fatigue = get_avg_tss(cursor, athlete_id, 7)
        # 状态值（status）
        status = fitness - fatigue

        # 写入或更新到 tb_athlete_daily_state
        cursor.execute("""
            REPLACE INTO tb_athlete_daily_state
            (athlete_id, date, status, fatigue, fitness)
            VALUES (%s, %s, %s, %s, %s)
        """, (athlete_id, today, status, fatigue, fitness))
        updated += 1

    conn.commit()
    cursor.close()
    conn.close()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ 成功更新 {updated}/{total} 位运动员。")

if __name__ == "__main__":
    update_daily_state()
