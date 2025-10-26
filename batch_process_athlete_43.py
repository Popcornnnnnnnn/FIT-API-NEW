#!/usr/bin/env python3
"""
批量处理运动员ID为43的所有活动
对每个活动调用 /all 接口，使用 Strava access_token
"""

import requests
import time
import json
import sys
from typing import List, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

# 导入配置
try:
    from batch_config import DB_CONFIG, API_CONFIG, PROCESSING_CONFIG
except ImportError:
    # 如果配置文件不存在，使用默认配置
    DB_CONFIG = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "password",
        "database": "fit_api_db"
    }
    API_CONFIG = {
        "base_url": "http://localhost:8000",
        "access_token": "5a173da68c14d5a5598477e617bd0349f6ae11ac"
    }
    PROCESSING_CONFIG = {
        "delay_seconds": 1.0,
        "timeout_seconds": 60,
        "max_activities": None,
        "athlete_id": 43
    }

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_process_athlete_43.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class Athlete43BatchProcessor:
    def __init__(self):
        """初始化批量处理器"""
        # 构建数据库连接URL
        db_url = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        
        self.api_base_url = API_CONFIG['base_url']
        self.access_token = API_CONFIG['access_token']
        self.athlete_id = PROCESSING_CONFIG['athlete_id']
        self.delay_seconds = PROCESSING_CONFIG['delay_seconds']
        self.timeout_seconds = PROCESSING_CONFIG['timeout_seconds']
        
        # 数据库连接
        self.engine = create_engine(db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # 统计信息
        self.stats = {
            'total_activities': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'skipped_calls': 0,
            'cache_hits': 0,
            'real_data_calls': 0,
            'total_duration': 0.0,
            'start_time': None,
            'end_time': None
        }
    
    def get_athlete_activities(self) -> List[Dict[str, Any]]:
        """获取运动员ID为43的所有活动"""
        try:
            with self.engine.connect() as conn:
                query = text("""
                    SELECT id, name, upload_fit_url, start_date, external_id
                    FROM tb_activity 
                    WHERE athlete_id = :athlete_id 
                    ORDER BY start_date DESC
                """)
                result = conn.execute(query, {"athlete_id": self.athlete_id})
                activities = []
                for row in result:
                    activities.append({
                        'id': row[0],
                        'name': row[1],
                        'upload_fit_url': row[2],
                        'start_date': row[3],
                        'external_id': row[4]
                    })
                return activities
        except Exception as e:
            logger.error(f"查询运动员活动失败: {e}")
            return []
    
    def call_activity_all_api(self, activity_id: int, activity_name: str = "") -> Dict[str, Any]:
        """调用单个活动的 /all 接口"""
        url = f"{self.api_base_url}/activities/{activity_id}/all"
        params = {
            'access_token': self.access_token,
            'resolution': 'high'
        }
        
        start_time = time.time()
        
        try:
            logger.info(f"正在处理活动 {activity_id}: {activity_name}")
            response = requests.get(url, params=params, timeout=self.timeout_seconds)
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                # 检查是否命中缓存
                response_data = response.json()
                cache_hit = False
                source_info = "未知"
                
                # 检查响应中是否包含缓存信息
                if 'data' in response_data and 'source' in response_data.get('data', {}):
                    source_info = response_data['data']['source']
                    cache_hit = source_info == "cache"
                
                # 检查响应头中的缓存信息
                cache_header = response.headers.get('X-Cache', '').lower()
                if 'hit' in cache_header:
                    cache_hit = True
                    source_info = "HTTP缓存"
                
                if cache_hit:
                    logger.info(f"✅ 活动 {activity_id} 处理成功 (缓存命中) - 耗时: {duration:.2f}秒")
                    self.stats['successful_calls'] += 1
                    self.stats['cache_hits'] = self.stats.get('cache_hits', 0) + 1
                else:
                    logger.info(f"✅ 活动 {activity_id} 处理成功 (实时数据) - 耗时: {duration:.2f}秒")
                    self.stats['successful_calls'] += 1
                    self.stats['real_data_calls'] = self.stats.get('real_data_calls', 0) + 1
                
                return {
                    'success': True,
                    'duration': duration,
                    'cache_hit': cache_hit,
                    'source': source_info
                }
            else:
                logger.error(f"❌ 活动 {activity_id} 处理失败: HTTP {response.status_code} - 耗时: {duration:.2f}秒")
                logger.error(f"错误响应: {response.text}")
                self.stats['failed_calls'] += 1
                return {
                    'success': False,
                    'duration': duration,
                    'error': f"HTTP {response.status_code}"
                }
                
        except requests.exceptions.Timeout:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"⏰ 活动 {activity_id} 请求超时 - 耗时: {duration:.2f}秒")
            self.stats['failed_calls'] += 1
            return {
                'success': False,
                'duration': duration,
                'error': 'timeout'
            }
        except requests.exceptions.RequestException as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"🌐 活动 {activity_id} 网络错误: {e} - 耗时: {duration:.2f}秒")
            self.stats['failed_calls'] += 1
            return {
                'success': False,
                'duration': duration,
                'error': str(e)
            }
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"💥 活动 {activity_id} 未知错误: {e} - 耗时: {duration:.2f}秒")
            self.stats['failed_calls'] += 1
            return {
                'success': False,
                'duration': duration,
                'error': str(e)
            }
    
    def process_all_activities(self, max_activities: int = None):
        """处理所有活动"""
        logger.info(f"开始处理运动员 {self.athlete_id} 的所有活动...")
        self.stats['start_time'] = time.time()
        
        # 获取活动列表
        activities = self.get_athlete_activities()
        if not activities:
            logger.warning(f"未找到运动员 {self.athlete_id} 的活动")
            return
        
        self.stats['total_activities'] = len(activities)
        logger.info(f"找到 {len(activities)} 个活动")
        
        # 限制处理数量（如果指定）
        if max_activities and max_activities < len(activities):
            activities = activities[:max_activities]
            logger.info(f"限制处理前 {max_activities} 个活动")
        
        # 逐个处理活动
        for i, activity in enumerate(activities, 1):
            activity_id = activity['id']
            activity_name = activity['name'] or f"活动{activity_id}"
            
            logger.info(f"进度: {i}/{len(activities)} - 处理活动 {activity_id}")
            
            # 调用API
            result = self.call_activity_all_api(activity_id, activity_name)
            
            # 累计总耗时
            if result['success']:
                self.stats['total_duration'] += result['duration']
            
            # 延迟（避免API限流）
            if i < len(activities):  # 最后一个不需要延迟
                self._countdown_wait(self.delay_seconds)
        
        self.stats['end_time'] = time.time()
        self.print_summary()
    
    def print_summary(self):
        """打印处理总结"""
        total_time = self.stats['end_time'] - self.stats['start_time']
        api_time = self.stats['total_duration']
        wait_time = total_time - api_time
        
        logger.info("=" * 60)
        logger.info("处理完成！统计信息:")
        logger.info(f"运动员ID: {self.athlete_id}")
        logger.info(f"总活动数: {self.stats['total_activities']}")
        logger.info(f"成功处理: {self.stats['successful_calls']}")
        logger.info(f"  - 缓存命中: {self.stats['cache_hits']}")
        logger.info(f"  - 实时数据: {self.stats['real_data_calls']}")
        logger.info(f"处理失败: {self.stats['failed_calls']}")
        logger.info(f"跳过处理: {self.stats['skipped_calls']}")
        logger.info(f"总耗时: {total_time:.2f} 秒")
        logger.info(f"  - API调用时间: {api_time:.2f} 秒")
        logger.info(f"  - 等待时间: {wait_time:.2f} 秒")
        if self.stats['successful_calls'] > 0:
            logger.info(f"平均每个活动API耗时: {api_time/self.stats['successful_calls']:.2f} 秒")
        logger.info(f"平均每个活动总耗时: {total_time/self.stats['total_activities']:.2f} 秒")
        logger.info("=" * 60)
    
    def _countdown_wait(self, seconds: float):
        """显示倒计时等待"""
        import sys
        
        logger.info(f"等待 {seconds} 秒...")
        
        # 如果等待时间很短，直接等待
        if seconds < 1:
            time.sleep(seconds)
            return
        
        # 显示倒计时
        for remaining in range(int(seconds), 0, -1):
            print(f"\r⏳ 等待中... {remaining} 秒", end="", flush=True)
            time.sleep(1)
        
        print("\r" + " " * 20 + "\r", end="", flush=True)  # 清除倒计时显示
    
    def test_single_activity(self, activity_id: int):
        """测试单个活动（用于调试）"""
        logger.info(f"测试单个活动 {activity_id}")
        result = self.call_activity_all_api(activity_id, f"测试活动{activity_id}")
        return result['success']

def main():
    """主函数"""
    # 命令行参数处理
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            # 测试模式：只处理一个活动
            if len(sys.argv) > 2:
                test_activity_id = int(sys.argv[2])
            else:
                test_activity_id = 106  # 默认测试活动ID
            
            processor = Athlete43BatchProcessor()
            processor.test_single_activity(test_activity_id)
            return
        elif sys.argv[1] == "help":
            print("用法:")
            print("  python batch_process_athlete_43.py                    # 处理所有活动")
            print("  python batch_process_athlete_43.py test [activity_id] # 测试单个活动")
            print("  python batch_process_athlete_43.py help               # 显示帮助")
            print("\n配置:")
            print("  请修改 batch_config.py 文件中的数据库连接信息")
            return
    
    # 创建处理器
    processor = Athlete43BatchProcessor()
    
    # 处理所有活动
    try:
        processor.process_all_activities(
            max_activities=PROCESSING_CONFIG.get('max_activities')  # 从配置文件读取限制
        )
    except KeyboardInterrupt:
        logger.info("用户中断处理")
        processor.print_summary()
    except Exception as e:
        logger.error(f"处理过程中发生错误: {e}")
        processor.print_summary()

if __name__ == "__main__":
    main()
