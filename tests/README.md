# 测试说明

## 测试结构

```
tests/
├── __init__.py              # 测试包初始化
├── conftest.py              # pytest配置和fixture (SQLite内存数据库)
├── conftest_mysql.py        # MySQL数据库测试配置
├── test_athletes.py         # 运动员相关接口测试
├── test_activities.py       # 活动相关接口测试
├── test_streams.py          # 数据流相关接口测试
├── test_uploads.py          # 文件上传相关接口测试
└── README.md               # 本文件
```

## 测试分类

### 1. 运动员接口测试 (`test_athletes.py`)
- **运动员创建测试**: 测试创建运动员的各种情况
- **运动员获取测试**: 测试获取单个运动员和运动员列表
- **运动员更新测试**: 测试更新运动员个人信息（FTP、最大心率、体重等）
- **运动员指标测试**: 测试添加运动员指标
- **数据验证测试**: 测试输入数据验证

### 2. 活动接口测试 (`test_activities.py`)
- **活动摘要测试**: 测试活动摘要数据（距离、时长、平均功率/心率等）
- **高级指标测试**: 测试NP、IF、TSS等高级指标
- **活动列表测试**: 测试活动列表获取

### 3. 数据流接口测试 (`test_streams.py`)
- **流数据测试**: 测试时间序列数据获取
- **批量流数据测试**: 测试多种流数据同时获取
- **采样率测试**: 测试不同采样率的数据

### 4. 文件上传接口测试 (`test_uploads.py`)
- **FIT文件上传测试**: 测试FIT文件上传功能
- **文件类型验证测试**: 测试非FIT文件的拒绝
- **上传状态测试**: 测试上传处理状态查询

## 运行测试

### 安装测试依赖
```bash
pip install pytest pytest-cov
```

### 运行所有测试
```bash
pytest
```

### 运行特定测试文件
```bash
pytest tests/test_users.py
```

### 运行特定测试类
```bash
pytest tests/test_users.py::TestUserCreation
```

### 运行特定测试方法
```bash
pytest tests/test_users.py::TestUserCreation::test_create_user_success
```

### 生成覆盖率报告
```bash
pytest --cov=app --cov-report=html
```

### 运行标记的测试
```bash
# 只运行单元测试
pytest -m unit

# 排除慢速测试
pytest -m "not slow"
```

## 测试数据

测试使用内存SQLite数据库，每个测试都会在独立的事务中运行，测试完成后自动回滚，确保测试之间相互独立。

## 扩展测试

### 添加新的测试文件
1. 在 `tests/` 目录下创建 `test_*.py` 文件
2. 按照现有模式组织测试类和方法
3. 使用 `client` fixture 进行HTTP请求测试

### 添加新的fixture
在 `conftest.py` 中添加新的fixture，供所有测试文件使用。

### 添加新的测试标记
在 `pytest.ini` 中添加新的markers定义。

## 注意事项

1. 所有测试都应该是独立的，不依赖其他测试的执行结果
2. 使用有意义的测试方法名称，描述测试的具体场景
3. 测试应该覆盖正常情况和异常情况
4. 定期运行测试，确保代码质量 