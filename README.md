# FIT文件分析API

一个用于分析FIT文件的后端接口实现，以Python语言为主。

## 🎯 项目概述

本项目提供完整的FIT文件分析功能，包括文件上传、数据解析、活动分析等核心功能。

### 主要功能
- 📤 **文件上传系统** - 支持FIT、TCX、GPX格式文件上传，包含重复文件检查
- 👥 **运动员管理** - 运动员信息管理和指标跟踪
- 📊 **活动分析** - 活动摘要和高级指标计算
- 📈 **数据流处理** - 时间序列数据流获取和分析
- 🗄️ **数据存储** - 文件数据Base64编码存储在数据库中

## 🏗️ 项目结构

```
FIT-API-NEW/
├── app/                          # 主应用代码
│   ├── __init__.py
│   ├── main.py                   # FastAPI应用入口
│   ├── db_base.py                # 数据库基础配置
│   ├── utils.py                  # 工具函数
│   │
│   ├── athletes/                 # 运动员模块
│   │   ├── __init__.py
│   │   ├── models.py             # 运动员数据模型
│   │   ├── schemas.py            # Pydantic模型
│   │   ├── crud.py               # 数据库操作
│   │   └── router.py             # API路由
│   │
│   ├── activities/               # 活动模块
│   │   ├── __init__.py
│   │   ├── models.py             # 活动数据模型
│   │   ├── schemas.py            # Pydantic模型
│   │   ├── crud.py               # 数据库操作
│   │   └── router.py             # API路由
│   │
│   ├── streams/                  # 数据流模块
│   │   ├── __init__.py
│   │   ├── schemas.py            # Pydantic模型
│   │   └── router.py             # API路由
│   │
│   └── uploads/                  # 文件上传模块
│       ├── __init__.py
│       ├── schemas.py            # Pydantic模型
│       └── router.py             # API路由
│
├── tests/                        # 测试套件
│   ├── __init__.py
│   ├── conftest.py               # pytest配置
│   │
│   ├── upload/                   # 上传功能测试
│   │   ├── __init__.py
│   │   ├── test_uploads.py       # 上传接口单元测试
│   │   └── local_fit_upload.py   # 本地FIT文件上传工具
│   │
│   ├── athletes/                 # 运动员功能测试
│   │   ├── __init__.py
│   │   └── test_athletes.py      # 运动员接口单元测试
│   │
│   ├── activities/               # 活动功能测试
│   │   ├── __init__.py
│   │   └── test_activities.py    # 活动接口单元测试
│   │
│   ├── streams/                  # 数据流功能测试
│   │   ├── __init__.py
│   │   └── test_streams.py       # 数据流接口单元测试
│   │
│   └── legacy/                   # 旧版本测试和示例
│       ├── __init__.py
│       ├── example_upload.py     # 完整示例脚本
│       ├── quick_upload_test.py  # 快速测试脚本
│       └── simple_example.py     # 简单使用示例
│
├── tools/                        # 工具脚本
│   └── db_viewer.py              # 数据库管理工具（查看、导出、清空）
│
├── fit_files/                    # FIT文件存储文件夹
├── requirements.txt              # Python依赖
├── .gitignore                   # Git忽略文件
└── README.md                    # 本文件
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd FIT-API-NEW

# 安装依赖
pip install -r requirements.txt

# 确保MySQL数据库运行
# 数据库配置在 app/utils.py 中
```

### 2. 启动API服务器

```bash
# 启动开发服务器
uvicorn app.main:app --reload

# 访问API文档
# http://localhost:8000/docs
```

### 3. 上传FIT文件

```bash
# 方法1: 使用本地上传工具
# 1. 将FIT文件放入 fit_files/ 文件夹
cp your_activity.fit fit_files/

# 2. 运行上传工具
python3 tests/upload/local_fit_upload.py

# 方法2: 使用API接口
curl -X POST "http://localhost:8000/uploads/" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@your_activity.fit" \
  -F "athlete_id=1" \
  -F "name=我的骑行活动"
```

### 4. 查看数据

```bash
# 使用数据库查看工具
python3 tools/db_viewer.py

# 或直接查询数据库
mysql -u root -p fitdb
SELECT * FROM activities ORDER BY created_at DESC;
```

## 📚 API接口

### 运动员管理

- `GET /athletes/` - 获取运动员列表
- `GET /athletes/{athlete_id}` - 获取运动员详情
- `POST /athletes/` - 创建运动员
- `PUT /athletes/{athlete_id}` - 更新运动员信息
- `POST /athletes/{athlete_id}/metrics` - 添加运动员指标

### 文件上传

- `POST /uploads/` - 上传文件（新接口）
- `POST /uploads/fit` - 上传FIT文件（旧接口）
- `GET /uploads/{activity_id}/status` - 获取上传状态

### 活动管理

- `GET /activities/` - 获取活动列表
- `GET /activities/{activity_id}` - 获取活动详情
- `GET /activities/{activity_id}/summary` - 获取活动摘要
- `GET /activities/{activity_id}/advanced` - 获取高级指标

### 数据流

- `GET /streams/{activity_id}` - 获取活动流数据
- `POST /streams/batch` - 批量获取流数据

## 🗄️ 数据库设计

### 主要表结构

#### `athletes` 表
```sql
CREATE TABLE athletes (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(256) NOT NULL,
    ftp FLOAT,
    max_hr INT,
    weight FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### `activities` 表
```sql
CREATE TABLE activities (
    id INT PRIMARY KEY AUTO_INCREMENT,
    athlete_id INT,
    file_data TEXT,           -- Base64编码的文件数据
    file_name VARCHAR(256),   -- 原始文件名
    name VARCHAR(256),        -- 活动名称
    description TEXT,         -- 活动描述
    data_type VARCHAR(32),    -- 文件格式
    external_id VARCHAR(256), -- 外部标识符
    status VARCHAR(32),       -- 处理状态
    error TEXT,               -- 错误信息
    trainer BOOLEAN,          -- 是否训练台
    commute BOOLEAN,          -- 是否通勤
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (athlete_id) REFERENCES athletes(id)
);
```

#### `athlete_metrics` 表
```sql
CREATE TABLE athlete_metrics (
    id INT PRIMARY KEY AUTO_INCREMENT,
    athlete_id INT,
    metric_name VARCHAR(256) NOT NULL,
    metric_value FLOAT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (athlete_id) REFERENCES athletes(id)
);
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定模块测试
python3 -m pytest tests/upload/ -v
python3 -m pytest tests/athletes/ -v
python3 -m pytest tests/activities/ -v
python3 -m pytest tests/streams/ -v

# 运行特定测试文件
python3 -m pytest tests/upload/test_uploads.py -v
```

### 测试覆盖

- **上传功能**: 8个测试
- **运动员功能**: 10个测试
- **活动功能**: 5个测试
- **数据流功能**: 5个测试
- **重复文件检查**: 3个测试
- **总计**: 31个测试

### 重复文件检查测试
```bash
# 运行重复文件检查测试
python3 -m pytest test/test_upload_duplicate.py -v
```

测试包括：
- 文件大小比较逻辑测试
- 重复文件检查逻辑测试
- 文件大小计算测试

## 🛠️ 工具脚本

### 数据库管理工具

#### 综合数据库管理工具
```bash
python3 tools/db_viewer.py
# 提供以下功能：
# 1. 查看数据库状态
# 2. 查看所有活动
# 3. 查看活动详情
# 4. 查看运动员
# 5. 查看表结构
# 6. 清空所有表
# 7. 删除并重新创建表
# 8. 重置自增ID
# 9. 清空activities表
```

### 文件上传工具

#### 本地FIT文件上传
```bash
# 1. 将FIT文件放入 fit_files/ 文件夹
# 2. 运行上传工具
python3 tests/upload/local_fit_upload.py
```

#### 示例脚本
```bash
# 简单示例
python3 tests/legacy/simple_example.py

# 完整示例
python3 tests/legacy/example_upload.py

# 快速测试
python3 tests/legacy/quick_upload_test.py

# 重复文件检查演示
python3 test/test_duplicate_example.py
```

## 📊 文件存储

### 数据库存储
- 文件以Base64编码存储在 `activities.file_data` 字段
- 支持FIT、TCX、GPX格式
- 文件大小建议不超过100MB

### 重复文件检查
系统实现了智能的重复文件检查机制：
- **文件名检查**: 检查同一运动员是否已上传同名文件
- **文件大小检查**: 比较文件大小，防止相同内容的重复上传
- **Base64解码验证**: 确保存储的文件数据完整性
- **错误处理**: 当文件数据损坏时，系统会记录警告但不会阻止上传

### 本地存储
- `fit_files/` - 待上传的FIT文件

## 🔧 配置

### 数据库配置
在 `app/utils.py` 中配置数据库连接：

```python
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:password@localhost/fitdb"
```

### 环境变量
建议使用环境变量配置敏感信息：

```bash
export DATABASE_URL="mysql+pymysql://user:pass@host/db"
export SECRET_KEY="your-secret-key"
```

## 🚨 注意事项

1. **数据备份** - 使用数据库清空工具前请备份重要数据
2. **文件大小** - 建议单个文件不超过100MB
3. **数据库权限** - 确保数据库用户有足够权限
4. **服务器运行** - 确保API服务器正在运行

## 🔮 扩展计划

- [ ] FIT文件解析功能
- [ ] 后台处理队列
- [ ] 文件压缩和优化
- [ ] 用户认证和权限
- [ ] 性能监控和日志
- [ ] Docker容器化部署

## 📝 更新日志

### v1.0.0 (当前版本)
- ✅ 基础API框架搭建
- ✅ 文件上传功能
- ✅ 运动员管理功能
- ✅ 活动管理功能
- ✅ 数据流功能
- ✅ 完整的测试套件
- ✅ 数据库管理工具
- ✅ 本地文件上传工具

## 🤝 贡献

欢迎提交Issue和Pull Request！

## �� 许可证

MIT License 

## 如何用 Postman 测试本项目 API

以下以常用的接口为例，演示如何用 Postman 进行完整测试：

### 1. 创建运动员
- **方法**：POST
- **URL**：`http://localhost:8000/athletes/`
- **Body**：选择 `raw` + `JSON`
```json
{
  "name": "测试运动员",
  "ftp": 250,
  "max_hr": 185,
  "weight": 70.0
}
```
- **返回**：包含 `id` 的运动员信息

### 2. 上传 FIT 文件
- **方法**：POST
- **URL**：`http://localhost:8000/uploads/`
- **Body**：选择 `form-data`
    - `file`（类型：File）：选择本地 `.fit` 文件
    - `name`（类型：Text，可选）：活动名称
    - `description`（类型：Text，可选）：活动描述
    - `data_type`（类型：Text，建议填 `fit`）
    - `athlete_id`（类型：Text）：上一步返回的运动员ID
- **返回**：包含 `activity_id` 的信息

### 3. 查询流数据
- **方法**：GET
- **URL**：`http://localhost:8000/activities/{activity_id}/streams`
- **Params**：
    - `keys`：如 `distance,heart_rate,power`（可多选，逗号分隔）
    - `resolution`：如 `high`、`medium`、`low`
- **示例**：
```
GET http://localhost:8000/activities/16/streams?keys=distance,heart_rate,power&resolution=high
```
- **返回**：
```json
[
  {
    "type": "distance",
    "data": [ ... ],
    "series_type": "distance",
    "original_size": 1000,
    "resolution": "high"
  },
  ...
]
```

### 4. 查询可用流类型
- **方法**：GET
- **URL**：`http://localhost:8000/activities/{activity_id}/streams/available`
- **返回**：
```json
{
  "activity_id": 16,
  "available_streams": ["distance", "heart_rate", ...],
  "total_streams": 9
}
```

---

#### Postman 使用技巧
- 上传文件时，`file` 字段类型要选 File，其他字段选 Text。
- GET 请求的参数建议用 Params 面板填写，多个 keys 用英文逗号分隔。
- 返回数据可直接在 Postman 的 Response 面板查看。

如需批量测试，可用 `tests/streams/fit_streams_test.py` 脚本自动上传和查询。

---

如有更多接口需求或遇到问题，欢迎随时反馈！ 