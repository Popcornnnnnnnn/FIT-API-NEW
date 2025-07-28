#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地FIT文件上传工具

这个脚本用于上传本地fit_files文件夹中的FIT文件。
支持批量上传和单个文件上传。
"""

import os
import requests
import glob
from pathlib import Path
from typing import List, Dict, Optional
import json

# API基础URL
BASE_URL = "http://localhost:8000"

class LocalFitUploader:
    """本地FIT文件上传器"""
    
    def __init__(self, fit_folder: str = "fit_files"):
        """
        初始化上传器
        
        Args:
            fit_folder: FIT文件所在文件夹路径
        """
        self.fit_folder = Path(fit_folder)
        self.uploaded_files = []
        self.failed_files = []
    
    def get_fit_files(self) -> List[Path]:
        """获取所有FIT文件"""
        if not self.fit_folder.exists():
            print(f"❌ 文件夹不存在: {self.fit_folder}")
            return []
        
        # 查找所有.fit文件
        fit_files = list(self.fit_folder.glob("*.fit"))
        fit_files.extend(self.fit_folder.glob("*.FIT"))
        
        print(f"📁 在 {self.fit_folder} 中找到 {len(fit_files)} 个FIT文件")
        return fit_files
    
    def create_athlete(self, name: str = "本地测试运动员") -> Optional[int]:
        """创建运动员"""
        athlete_data = {
            "name": name,
            "ftp": 250.0,
            "max_hr": 185,
            "weight": 70.5
        }
        
        try:
            response = requests.post(f"{BASE_URL}/athletes/", json=athlete_data)
            if response.status_code == 200:
                athlete = response.json()
                print(f"✅ 运动员创建成功: {athlete['name']} (ID: {athlete['id']})")
                return athlete['id']
            else:
                print(f"❌ 运动员创建失败: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 创建运动员时发生错误: {e}")
            return None
    
    def upload_single_file(self, file_path: Path, athlete_id: int, **kwargs) -> Optional[Dict]:
        """上传单个文件"""
        try:
            with open(file_path, 'rb') as f:
                files = {"file": (file_path.name, f, "application/octet-stream")}
                
                # 准备表单数据
                data = {
                    "athlete_id": athlete_id,
                    "name": kwargs.get("name", file_path.stem),
                    "description": kwargs.get("description", f"本地文件: {file_path.name}"),
                    "trainer": kwargs.get("trainer", "false"),
                    "commute": kwargs.get("commute", "false"),
                    "data_type": "fit",
                }
                
                if "external_id" in kwargs:
                    data["external_id"] = kwargs["external_id"]
                
                response = requests.post(f"{BASE_URL}/uploads/", files=files, data=data)
                
                if response.status_code == 200:
                    result = response.json()
                    # 检查API返回的状态
                    if result.get('status') == 'failed' or result.get('activity_id') == 0:
                        print(f"❌ 文件上传失败: {file_path.name}")
                        print(f"   - Activity ID: {result.get('activity_id')}")
                        print(f"   - Status: {result.get('status')}")
                        if result.get('error'):
                            print(f"   - Error: {result.get('error')}")
                        return None
                    else:
                        print(f"✅ 文件上传成功: {file_path.name}")
                        print(f"   - Activity ID: {result['activity_id']}")
                        print(f"   - Status: {result['status']}")
                        return result
                else:
                    print(f"❌ 文件上传失败: {file_path.name}")
                    print(f"   Error: {response.text}")
                    return None
                    
        except Exception as e:
            print(f"❌ 上传文件时发生错误 {file_path.name}: {e}")
            return None
    
    def upload_all_files(self, athlete_id: int, **kwargs) -> Dict:
        """上传所有FIT文件"""
        fit_files = self.get_fit_files()
        
        if not fit_files:
            print("没有找到FIT文件")
            return {"uploaded": [], "failed": []}
        
        print(f"\n🚀 开始上传 {len(fit_files)} 个文件...")
        
        for i, file_path in enumerate(fit_files, 1):
            print(f"\n[{i}/{len(fit_files)}] 上传: {file_path.name}")
            
            # 为每个文件生成唯一的外部ID
            external_id = f"local-{file_path.stem}-{i}"
            
            result = self.upload_single_file(
                file_path, 
                athlete_id, 
                external_id=external_id,
                **kwargs
            )
            
            if result and result.get('status') != 'failed' and result.get('activity_id') != 0:
                self.uploaded_files.append({
                    "file": file_path.name,
                    "activity_id": result["activity_id"],
                    "external_id": result["external_id"]
                })
            else:
                self.failed_files.append(file_path.name)
        
        return self.get_upload_summary()
    
    def upload_specific_files(self, file_names: List[str], athlete_id: int, **kwargs) -> Dict:
        """上传指定的文件"""
        fit_files = self.get_fit_files()
        target_files = []
        
        for file_name in file_names:
            file_path = self.fit_folder / file_name
            if file_path in fit_files:
                target_files.append(file_path)
            else:
                print(f"⚠️  文件不存在: {file_name}")
        
        if not target_files:
            print("没有找到指定的文件")
            return {"uploaded": [], "failed": []}
        
        print(f"\n🚀 开始上传指定的 {len(target_files)} 个文件...")
        
        for i, file_path in enumerate(target_files, 1):
            print(f"\n[{i}/{len(target_files)}] 上传: {file_path.name}")
            
            external_id = f"local-{file_path.stem}-{i}"
            
            result = self.upload_single_file(
                file_path, 
                athlete_id, 
                external_id=external_id,
                **kwargs
            )
            
            if result and result.get('status') != 'failed' and result.get('activity_id') != 0:
                self.uploaded_files.append({
                    "file": file_path.name,
                    "activity_id": result["activity_id"],
                    "external_id": result["external_id"]
                })
            else:
                self.failed_files.append(file_path.name)
        
        return self.get_upload_summary()
    
    def get_upload_summary(self) -> Dict:
        """获取上传摘要"""
        return {
            "uploaded": self.uploaded_files,
            "failed": self.failed_files,
            "total_uploaded": len(self.uploaded_files),
            "total_failed": len(self.failed_files)
        }
    
    def save_upload_log(self, filename: str = "upload_log.json"):
        """保存上传日志"""
        log_data = {
            "uploaded_files": self.uploaded_files,
            "failed_files": self.failed_files,
            "summary": self.get_upload_summary()
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        print(f"📝 上传日志已保存到: {filename}")

def main():
    """主函数"""
    print("🚀 本地FIT文件上传工具")
    print("=" * 50)
    
    # 检查服务器状态
    try:
        response = requests.get(f"{BASE_URL}/docs")
        if response.status_code != 200:
            print("❌ API服务器未运行，请先启动服务器")
            print("   启动命令: uvicorn app.main:app --reload")
            return
    except:
        print("❌ 无法连接到API服务器")
        print("   请确保服务器运行在 http://localhost:8000")
        return
    
    # 创建上传器
    uploader = LocalFitUploader()
    
    # 检查FIT文件
    fit_files = uploader.get_fit_files()
    if not fit_files:
        print(f"\n💡 提示:")
        print(f"1. 请将FIT文件放入 {uploader.fit_folder} 文件夹")
        print(f"2. 支持的文件格式: .fit, .FIT")
        print(f"3. 重新运行此脚本")
        return
    
    # 显示找到的文件
    print("\n📋 找到的FIT文件:")
    for i, file_path in enumerate(fit_files, 1):
        file_size = file_path.stat().st_size
        print(f"   {i}. {file_path.name} ({file_size} bytes)")
    
    # 创建运动员
    print(f"\n👤 创建运动员...")
    athlete_id = uploader.create_athlete()
    if not athlete_id:
        print("无法继续，运动员创建失败")
        return
    
    # 询问上传方式
    print(f"\n选择上传方式:")
    print(f"1. 上传所有文件")
    print(f"2. 上传指定文件")
    
    choice = input("请输入选择 (1 或 2): ").strip()
    
    if choice == "1":
        # 上传所有文件
        result = uploader.upload_all_files(athlete_id)
    elif choice == "2":
        # 上传指定文件
        print(f"\n请输入要上传的文件编号 (用空格分隔，如: 1 3 5):")
        print("   文件编号即上面列表前面的数字（按文件夹中的顺序排列）")
        file_indices = input("文件编号: ").strip().split()
        
        try:
            selected_files = [fit_files[int(idx)-1].name for idx in file_indices if 1 <= int(idx) <= len(fit_files)]
            result = uploader.upload_specific_files(selected_files, athlete_id)
        except (ValueError, IndexError):
            print("❌ 无效的文件编号")
            return
    else:
        print("❌ 无效的选择")
        return
    
    # 显示结果
    print(f"\n📊 上传结果:")
    print(f"✅ 成功上传: {result['total_uploaded']} 个文件")
    print(f"❌ 上传失败: {result['total_failed']} 个文件")
    
    if result['uploaded']:
        print(f"\n✅ 成功上传的文件:")
        for item in result['uploaded']:
            print(f"   - {item['file']} (Activity ID: {item['activity_id']})")
    
    if result['failed']:
        print(f"\n❌ 上传失败的文件:")
        for file_name in result['failed']:
            print(f"   - {file_name}")
    
    # 保存日志
    uploader.save_upload_log()
    
    print(f"\n🎉 上传完成!")

if __name__ == "__main__":
    main() 