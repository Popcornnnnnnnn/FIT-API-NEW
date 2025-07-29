#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库管理工具

用于查看和管理数据库中的文件信息
包含查看、导出、清空等功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
# from app.utils import SQLALCHEMY_DATABASE_URL  # 移除
import base64
from pathlib import Path
from urllib.parse import quote_plus

# 数据库连接字符串，优先读取环境变量
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    password = "plz@myshit"
    encoded_password = quote_plus(password)
    DATABASE_URL = f"mysql+pymysql://root:{encoded_password}@localhost/fitdb"

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        """初始化数据库连接"""
        self.engine = create_engine(DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_activities_summary(self):
        """获取活动摘要"""
        with self.SessionLocal() as session:
            # 查询所有活动
            result = session.execute(text("""
                SELECT 
                    id, 
                    athlete_id, 
                    file_name, 
                    name, 
                    data_type, 
                    status, 
                    created_at,
                    LENGTH(file_data) as file_size_bytes
                FROM activities 
                ORDER BY created_at DESC
            """))
            
            activities = result.fetchall()
            return activities
    
    def get_activity_detail(self, activity_id: int):
        """获取活动详情"""
        with self.SessionLocal() as session:
            result = session.execute(text("""
                SELECT 
                    a.id, 
                    a.athlete_id, 
                    a.file_name, 
                    a.name, 
                    a.description,
                    a.data_type, 
                    a.status, 
                    a.error,
                    a.external_id,
                    a.trainer,
                    a.commute,
                    a.created_at,
                    LENGTH(a.file_data) as file_size_bytes,
                    ath.name as athlete_name
                FROM activities a
                LEFT JOIN athletes ath ON a.athlete_id = ath.id
                WHERE a.id = :activity_id
            """), {"activity_id": activity_id})
            
            activity = result.fetchone()
            return activity
    

    
    def get_athletes_summary(self):
        """获取运动员摘要"""
        with self.SessionLocal() as session:
            try:
                result = session.execute(text("""
                    SELECT 
                        id, 
                        name, 
                        ftp, 
                        max_hr, 
                        weight,
                        (SELECT COUNT(*) FROM activities WHERE athlete_id = athletes.id) as activity_count
                    FROM athletes 
                    ORDER BY id
                """))
                
                athletes = result.fetchall()
                return athletes
            except Exception:
                # 如果activities表不存在，使用简化查询
                result = session.execute(text("""
                    SELECT 
                        id, 
                        name, 
                        ftp, 
                        max_hr, 
                        weight,
                        0 as activity_count
                    FROM athletes 
                    ORDER BY id
                """))
                
                athletes = result.fetchall()
                return athletes
    
    def get_database_status(self):
        """获取数据库状态"""
        with self.SessionLocal() as session:
            # 获取各表的记录数
            try:
                activities_count = session.execute(text("SELECT COUNT(*) FROM activities")).scalar()
            except Exception:
                activities_count = 0  # activities表不存在
            
            athletes_count = session.execute(text("SELECT COUNT(*) FROM athletes")).scalar()
            metrics_count = session.execute(text("SELECT COUNT(*) FROM athlete_metrics")).scalar()
            
            return {
                "activities": activities_count,
                "athletes": athletes_count,
                "athlete_metrics": metrics_count,
                "total": activities_count + athletes_count + metrics_count
            }
    
    def clear_all_tables(self):
        """清空所有表（保留表结构）"""
        with self.SessionLocal() as session:
            try:
                # 按外键约束顺序删除
                session.execute(text("DELETE FROM athlete_metrics"))
                session.execute(text("DELETE FROM activities"))
                session.execute(text("DELETE FROM athletes"))
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                raise e
    

    
    def drop_and_recreate_tables(self):
        """删除并重新创建所有表"""
        from app.db_base import Base
        from app.athletes.models import Athlete, AthleteMetric
        from app.activities.models import Activity
        
        try:
            # 删除所有表
            Base.metadata.drop_all(bind=self.engine)
            
            # 重新创建所有表
            Base.metadata.create_all(bind=self.engine)
            
            return True
        except Exception as e:
            raise e
    
    def reset_auto_increment(self):
        """重置自增ID"""
        with self.SessionLocal() as session:
            try:
                session.execute(text("ALTER TABLE athlete_metrics AUTO_INCREMENT = 1"))
                session.execute(text("ALTER TABLE activities AUTO_INCREMENT = 1"))
                session.execute(text("ALTER TABLE athletes AUTO_INCREMENT = 1"))
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                raise e
    
    def clear_activities_table(self):
        """清空activities表（保留表结构）"""
        with self.SessionLocal() as session:
            try:
                # 清空activities表的所有数据，但保留表结构
                session.execute(text("DELETE FROM activities"))
                # 重置自增ID
                session.execute(text("ALTER TABLE activities AUTO_INCREMENT = 1"))
                session.commit()
                return True
            except Exception as e:
                session.rollback()
                raise e
    
    def get_table_structure(self, table_name: str = None):
        """获取表结构"""
        with self.SessionLocal() as session:
            if table_name:
                # 获取指定表的结构
                result = session.execute(text(f"DESCRIBE {table_name}"))
                columns = result.fetchall()
                return {table_name: columns}
            else:
                # 获取所有表的结构
                tables = ['athletes', 'athlete_metrics']
                structures = {}
                
                for table in tables:
                    try:
                        result = session.execute(text(f"DESCRIBE {table}"))
                        columns = result.fetchall()
                        structures[table] = columns
                    except Exception:
                        # 如果表不存在，跳过
                        continue
                
                # 检查activities表是否存在
                try:
                    result = session.execute(text("DESCRIBE activities"))
                    columns = result.fetchall()
                    structures['activities'] = columns
                except Exception:
                    # activities表不存在
                    pass
                    
                return structures

def main():
    """主函数"""
    print("🔍 数据库管理工具")
    print("=" * 50)
    
    manager = DatabaseManager()
    
    while True:
        print(f"\n选择操作:")
        print(f"1. 查看数据库状态")
        print(f"2. 查看所有活动")
        print(f"3. 查看活动详情")
        print(f"4. 查看运动员")
        print(f"5. 查看表结构")
        print(f"6. 清空所有表")
        print(f"7. 删除并重新创建表")
        print(f"8. 重置自增ID")
        print(f"9. 清空activities表")
        print(f"0. 退出")
        
        choice = input("\n请输入选择: ").strip()
        
        if choice == "1":
            # 查看数据库状态
            status = manager.get_database_status()
            print(f"\n📊 当前数据库状态:")
            print("=" * 50)
            print(f"📋 activities: {status['activities']} 条记录")
            print(f"📋 athlete_metrics: {status['athlete_metrics']} 条记录")
            print(f"📋 athletes: {status['athletes']} 条记录")
            print("-" * 50)
            print(f"📈 总计: {status['total']} 条记录")
        
        elif choice == "2":
            # 查看所有活动
            try:
                activities = manager.get_activities_summary()
                print(f"\n📋 所有活动 ({len(activities)} 个):")
                print("-" * 80)
                print(f"{'ID':<4} {'运动员ID':<8} {'文件名':<20} {'名称':<15} {'类型':<6} {'状态':<10} {'大小(KB)':<10}")
                print("-" * 80)
                
                for activity in activities:
                    size_kb = activity.file_size_bytes // 1024 if activity.file_size_bytes else 0
                    print(f"{activity.id:<4} {activity.athlete_id:<8} {activity.file_name:<20} {activity.name:<15} {activity.data_type:<6} {activity.status:<10} {size_kb:<10}")
            except Exception as e:
                print(f"❌ 无法查看活动: {e}")
                print("可能activities表不存在")
        
        elif choice == "3":
            # 查看活动详情
            try:
                activity_id = input("请输入活动ID: ").strip()
                activity_id = int(activity_id)
                activity = manager.get_activity_detail(activity_id)
                
                if activity:
                    print(f"\n📄 活动详情 (ID: {activity_id}):")
                    print("-" * 50)
                    print(f"运动员: {activity.athlete_name} (ID: {activity.athlete_id})")
                    print(f"文件名: {activity.file_name}")
                    print(f"名称: {activity.name}")
                    print(f"描述: {activity.description}")
                    print(f"类型: {activity.data_type}")
                    print(f"状态: {activity.status}")
                    print(f"外部ID: {activity.external_id}")
                    print(f"训练台: {activity.trainer}")
                    print(f"通勤: {activity.commute}")
                    print(f"文件大小: {activity.file_size_bytes} bytes")
                    print(f"创建时间: {activity.created_at}")
                    if activity.error:
                        print(f"错误: {activity.error}")
                else:
                    print(f"❌ 未找到活动ID: {activity_id}")
            except ValueError:
                print("❌ 无效的活动ID")
            except Exception as e:
                print(f"❌ 无法查看活动详情: {e}")
                print("可能activities表不存在")
        
        elif choice == "4":
            # 查看运动员
            athletes = manager.get_athletes_summary()
            print(f"\n👥 所有运动员 ({len(athletes)} 个):")
            print("-" * 70)
            print(f"{'ID':<4} {'姓名':<15} {'FTP':<6} {'最大心率':<8} {'体重':<6} {'活动数':<6}")
            print("-" * 70)
            
            for athlete in athletes:
                print(f"{athlete.id:<4} {athlete.name:<15} {athlete.ftp or '-':<6} {athlete.max_hr or '-':<8} {athlete.weight or '-':<6} {athlete.activity_count:<6}")
        
        elif choice == "5":
            # 查看表结构
            print("\n选择要查看的表结构:")
            print("1. 查看所有表结构")
            print("2. 查看 athletes 表结构")
            print("3. 查看 athlete_metrics 表结构")
            print("4. 查看 activities 表结构")
            
            table_choice = input("请输入选择: ").strip()
            
            if table_choice == "1":
                structures = manager.get_table_structure()
                for table_name, columns in structures.items():
                    print(f"\n📋 {table_name} 表结构:")
                    print("-" * 80)
                    print(f"{'字段名':<20} {'类型':<20} {'NULL':<8} {'KEY':<8} {'DEFAULT':<12} {'EXTRA':<10}")
                    print("-" * 80)
                    for col in columns:
                        print(f"{col[0]:<20} {col[1]:<20} {col[2]:<8} {col[3]:<8} {str(col[4]):<12} {col[5]:<10}")
            elif table_choice == "2":
                structures = manager.get_table_structure("athletes")
                table_name, columns = list(structures.items())[0]
                print(f"\n📋 {table_name} 表结构:")
                print("-" * 80)
                print(f"{'字段名':<20} {'类型':<20} {'NULL':<8} {'KEY':<8} {'DEFAULT':<12} {'EXTRA':<10}")
                print("-" * 80)
                for col in columns:
                    print(f"{col[0]:<20} {col[1]:<20} {col[2]:<8} {col[3]:<8} {str(col[4]):<12} {col[5]:<10}")
            elif table_choice == "3":
                structures = manager.get_table_structure("athlete_metrics")
                table_name, columns = list(structures.items())[0]
                print(f"\n📋 {table_name} 表结构:")
                print("-" * 80)
                print(f"{'字段名':<20} {'类型':<20} {'NULL':<8} {'KEY':<8} {'DEFAULT':<12} {'EXTRA':<10}")
                print("-" * 80)
                for col in columns:
                    print(f"{col[0]:<20} {col[1]:<20} {col[2]:<8} {col[3]:<8} {str(col[4]):<12} {col[5]:<10}")
            elif table_choice == "4":
                structures = manager.get_table_structure("activities")
                table_name, columns = list(structures.items())[0]
                print(f"\n📋 {table_name} 表结构:")
                print("-" * 80)
                print(f"{'字段名':<20} {'类型':<20} {'NULL':<8} {'KEY':<8} {'DEFAULT':<12} {'EXTRA':<10}")
                print("-" * 80)
                for col in columns:
                    print(f"{col[0]:<20} {col[1]:<20} {col[2]:<8} {col[3]:<8} {str(col[4]):<12} {col[5]:<10}")
            else:
                print("❌ 无效的选择")
        
        elif choice == "6":
            # 清空所有表
            print("⚠️  警告：即将清空所有表")
            confirm = input("请输入 'YES' 确认，或按回车取消: ").strip()
            if confirm == "YES":
                try:
                    manager.clear_all_tables()
                    print("✅ 成功清空所有表")
                except Exception as e:
                    print(f"❌ 清空表时发生错误: {e}")
            else:
                print("❌ 操作已取消")
        
        elif choice == "7":
            # 删除并重新创建表
            print("⚠️  警告：即将删除并重新创建所有表")
            confirm = input("请输入 'YES' 确认，或按回车取消: ").strip()
            if confirm == "YES":
                try:
                    manager.drop_and_recreate_tables()
                    print("✅ 成功删除并重新创建所有表")
                except Exception as e:
                    print(f"❌ 重新创建表时发生错误: {e}")
            else:
                print("❌ 操作已取消")
        
        elif choice == "8":
            # 重置自增ID
            print("🔄 重置自增ID...")
            try:
                manager.reset_auto_increment()
                print("✅ 成功重置自增ID")
            except Exception as e:
                print(f"❌ 重置自增ID时发生错误: {e}")
        
        elif choice == "9":
            # 清空activities表
            print("⚠️  警告：即将清空activities表的所有数据（保留表结构）")
            confirm = input("请输入 'YES' 确认，或按回车取消: ").strip()
            if confirm == "YES":
                try:
                    manager.clear_activities_table()
                    print("✅ 成功清空activities表")
                except Exception as e:
                    print(f"❌ 清空activities表时发生错误: {e}")
            else:
                print("❌ 操作已取消")
        
        elif choice == "0":
            print("👋 再见!")
            break
        
        else:
            print("❌ 无效的选择")

if __name__ == "__main__":
    main() 