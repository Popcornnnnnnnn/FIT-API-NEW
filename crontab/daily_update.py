#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import pymysql
from datetime import date, timedelta, datetime

# === 数据库配置 ===
# 注意：生产环境建议将敏感信息（如密码）放在环境变量或配置文件中
DB_CONFIG = {
    "host": "121.41.238.53",      # 数据库主机地址
    "user": "root",            # 数据库用户名
    "password": "86230ce6558fd9a1",  # 数据库密码
    "database": "ry-system",   # 数据库名称
    "charset": "utf8mb4"       # 字符集，支持 emoji 等特殊字符
}


def get_connection():
    return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)


def get_avg_tss(cursor, athlete_id, days):
    """
    计算指定运动员最近 N 天内的平均TSS（按天数平均）
    
    注意：这里计算的是"总TSS / 天数"，而不是"活动TSS的平均值"
    例如：7天内总TSS=700，则返回 700/7=100，而不是 700/活动数量
    
    参数：
        cursor: 数据库游标对象
        athlete_id: 运动员ID
        days: 天数范围（例如：7 表示最近 7 天）
    
    返回：
        float: 平均TSS（总TSS除以天数），如果没有记录则返回0.0
    """
    now = datetime.now()                    # 当前时间
    start_time = now - timedelta(days=days)  # 计算 N 天前的时间
    
    # 使用 SUM 求和，查询条件包含上限
    # 与 activity_service.py 中的 _update_athlete_status 保持一致
    # 注意：只计算 tss IS NOT NULL 且 tss > 0 的记录
    cursor.execute("""
        SELECT SUM(tss) AS sum_tss
        FROM tb_activity
        WHERE athlete_id = %s
          AND start_date >= %s
          AND start_date <= %s
          AND tss IS NOT NULL
          AND tss > 0
    """, (athlete_id, start_time, now))
    
    row = cursor.fetchone()
    
    # 如果没有记录或总和为 None，返回 0.0
    if not row or row["sum_tss"] is None:
        return 0.0
    
    # 返回：总TSS / 天数
    return float(row["sum_tss"]) / days


def update_daily_state():

    conn = get_connection()
    cursor = conn.cursor()
    today = date.today()  
    cursor.execute("SELECT id FROM tb_athlete")
    all_rows = cursor.fetchall()
    athlete_ids = [row["id"] for row in all_rows]

    total = len(athlete_ids)  
    updated = 0               

    for athlete_id in athlete_ids:
        fitness = int(get_avg_tss(cursor, athlete_id, 42))
        fatigue = int(get_avg_tss(cursor, athlete_id, 7))
        status = fitness - fatigue
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
