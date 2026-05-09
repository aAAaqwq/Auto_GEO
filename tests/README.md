# AutoGeo 测试目录

## 目录结构

```
tests/
├── README.md                 # 本文件
├── conftest.py              # pytest全局配置
├── e2e/                     # 端到端测试 (Playwright)
│   └── data-report.spec.ts  # 数据报表E2E测试
├── unit/                    # 单元测试
│   ├── test_accounts.py     # 账号相关测试
│   ├── test_account_data.py # 账号数据测试
│   ├── test_account_validation.py # 账号验证测试
│   ├── test_article_collection.py # 文章收集测试
│   ├── test_reports.py      # 报表测试
│   └── test_storage_structure.py  # 存储结构测试
├── integration/             # 集成测试
│   └── api/                 # API集成测试
│       └── test_reports_api.py
├── scripts/                 # 脚本测试
│   ├── test_zhihu.py        # 知乎脚本测试
│   └── test_zhihu_full.py   # 知乎完整测试
├── screenshots/             # 测试截图
│   ├── zhihu_fixed.png
│   ├── zhihu_image_upload.png
│   ├── zhihu_publish_test.png
│   └── zhihu_research.png
└── utils/                   # 测试工具
    └── sync_zhihu_to_ragflow.py  # 知乎数据同步到RAGFlow
```

## 测试类型

### 单元测试
使用 pytest 运行：
```bash
cd tests
pytest unit/ -v
```

### 集成测试
```bash
cd tests
pytest integration/ -v
```

### E2E测试
使用 Playwright：
```bash
cd tests/e2e
npx playwright test
```

### 脚本测试
```bash
cd tests
python scripts/test_zhihu.py
```

## 测试配置

- **pytest配置**: `conftest.py`
- **Playwright配置**: `../frontend/playwright.config.ts`

## 截图说明

`screenshots/` 目录存放测试过程中生成的截图，用于：
- 测试报告展示
- 问题排查
- 文档说明

## 运行所有测试

```bash
# 后端测试
pytest tests/ -v --cov=backend

# 前端E2E测试
cd frontend && npx playwright test
```
