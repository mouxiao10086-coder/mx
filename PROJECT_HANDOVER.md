# 甲方后台定时查询工具 - 项目交接文档

> **文档版本**: v2.0  
> **更新时间**: 2026-05-28  
> **项目状态**: 多用户改造进行中 (80%完成)  
> **目标读者**: AI模型/开发者/运维人员  

---

## 📋 目录

1. [项目概述](#1-项目概述)
2. [技术栈详解](#2-技术栈详解)
3. [项目结构](#3-项目结构)
4. [数据库设计](#4-数据库设计)
5. [API接口文档](#5-api接口文档)
6. [前端功能说明](#6-前端功能说明)
7. [部署指南](#7-部署指南)
8. [开发指南](#8-开发指南)
9. [待完成任务清单](#9-待完成任务清单)
10. [常见问题排查](#10-常见问题排查)
11. [快速上手检查清单](#11-快速上手检查清单)

---

## 1. 项目概述

### 1.1 项目背景

**甲方后台定时查询工具** 是一个用于自动化采集巴西Slos游戏产品报表数据的Web应用。

**核心功能**:
- 通过内网API自动采集产品数据（访问/注册/首充）
- 支持多用户隔离（每个用户只能看到自己的产品和data）
- 定时任务管理（每小时自动采集）
- 数据查询和展示
- 管理员面板（用户管理/全局产品视图/系统日志）

**目标用户**:
- 巴西Slos游戏广告投放团队
- 需要监控多个产品数据的运营人员

### 1.2 核心业务流程

```
1. 用户添加产品（粘贴查询链接，自动解析参数）
   ↓
2. 系统定时采集数据（北京时间 00-09点、18-23点的50分）
   ↓
3. 数据存储到SQLite数据库
   ↓
4. 用户在前端查询和展示数据
```

### 1.3 技术架构图

```
┌─────────────────────────────────────────────────────────┐
│                       用户浏览器                        │
│  ┌──────────────┐      ┌──────────────┐             │
│  │  login.html   │      │  index.html  │             │
│  │  (登录页面)    │ ───→ │  (主界面)      │             │
│  └──────────────┘      └──────────────┘             │
└─────────────────────────────────────────────────────────┘
                          ↓ HTTP Requests (with Token)
┌─────────────────────────────────────────────────────────┐
│                  腾讯云服务器 (Ubuntu 22.04)           │
│  ┌──────────────────────────────────────────────────┐  │
│  │  server.py (Flask, 端口 8991)                   │  │
│  │    - 登录/登出接口                                │  │
│  │    - Token验证中间件                               │  │
│  │    - 静态文件服务                                 │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  api.py (业务逻辑层)                             │  │
│  │    - 用户认证 ( login/verify)                    │  │
│  │    - 产品管理 (CRUD)                            │  │
│  │    - 数据采集 (fetch_now/test_connection)         │  │
│  │    - 数据查询 (get_data)                        │  │
│  │    - 管理员接口 (admin/*)                       │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  db.py (数据库操作层)                           │  │
│  │    - SQLite数据库 (app.db)                      │  │
│  │    - 用户/产品/定时任务/数据/日志 操作           │  │
│  └──────────────────────────────────────────────────┘  │
│                          ↓                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  fetch_reports.py (数据采集脚本)                 │  │
│  │    - 从数据库读取产品配置                        │  │
│  │    - 调用内网API采集数据                        │  │
│  │    - 保存数据到数据库                           │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              内网报表API (16.163.114.99:8990)         │
│  - reportniunai.php (G45, 82B产品)                  │
│  - reportzhugan.php (35X产品)                        │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 技术栈详解

### 2.1 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.9.6 | 服务端编程语言 |
| **Flask** | 2.3.3 | Web框架 (server.py) |
| **sqlite3** | 内置 | 数据库 (SQLite) |
| **hashlib** | 内置 | 密码哈希 (SHA256) |
| **APScheduler** | 3.10.4 | 定时任务调度器 (计划中) |
| **requests** | 2.31.0 | HTTP请求库 (调用内网API) |

### 2.2 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| **Vue 3** | 3.3.4 | 响应式前端框架 (CDN引入) |
| **Tailwind CSS** | 3.3.5 | 实用优先的CSS框架 (CDN引入) |
| **localStorage** | - | Token存储 |

### 2.3 数据库

| 技术 | 版本 | 用途 |
|------|------|------|
| **SQLite** | 3.37.0 | 轻量级嵌入式数据库 |
| **数据库文件** | - | `/opt/report-tool/data/app.db` |

### 2.4 部署

| 技术 | 版本 | 用途 |
|------|------|------|
| **服务器** | - | 腾讯云轻量应用服务器 (香港) |
| **操作系统** | Ubuntu 22.04 LTS | Linux发行版 |
| **Web服务** | Flask内置 | 开发环境 (计划用Gunicorn) |
| **进程管理** | systemd | 服务开机自启/崩溃重启 |
| **SSH** | - | 远程连接 (密码登录) |

---

## 3. 项目结构

### 3.1 服务器文件结构

```
/opt/report-tool/           # 项目根目录
├── server.py               # HTTP服务 (Flask, 端口8991)
├── api.py                  # 后端API业务逻辑
├── db.py                   # 数据库操作层
├── fetch_reports.py        # 数据采集脚本
├── fetch_cron.sh          # cron执行脚本
├── data/                   # 数据目录
│   ├── app.db             # SQLite数据库文件
│   └── app_config.json    # 应用配置文件 (计划中)
├── web/                    # 前端文件目录
│   ├── login.html         # 登录页面
│   └── index.html        # 主界面
├── logs/                   # 日志目录 (计划中)
│   └── app.log
└── venv/                  # Python虚拟环境 (计划中)
```

### 3.2 本地开发文件结构

```
~/WorkBuddy/data/          # 本地开发目录
├── server.py               # HTTP服务
├── api.py                  # 后端API
├── db.py                   # 数据库操作层
├── fetch_reports.py        # 数据采集脚本
├── fetch_cron.sh          # cron执行脚本
├── web/                    # 前端文件
│   ├── login.html         # 登录页面
│   └── index.html        # 主界面
├── data/                   # 本地测试数据库
│   └── app.db
└── PROJECT_HANDOVER.md   # 本文档
```

### 3.3 文件功能说明

#### `server.py` - HTTP服务

**功能**:
- 提供Flask Web服务 (端口8991)
- 处理用户登录/登出请求
- 验证Token (所有API请求)
- 静态文件服务 (login.html, index.html)
- 路由转发到 `api.py`

**关键代码段**:
```python
# Token验证中间件
@app.before_request
def verify_token():
    if request.path.startswith('/api/') and request.path not in ['/api/login', '/api/register']:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token or token != 'test-token-123':  # 简化示例
            return jsonify({'ok': False, 'error': '未登录'}), 401
        # 从Token解析user_id (实际应该用JWT或数据库验证)
        request.user_id = 1  # 简化示例
```

#### `api.py` - 后端API业务逻辑

**功能**:
- 用户管理 (注册/登录/验证)
- 产品管理 (添加/编辑/删除/查询)
- 数据采集 (立即采集/测试连接)
- 数据查询 (按日期/产品查询)
- 定时任务管理 (设置/删除/查询)
- 管理员功能 (用户管理/全局产品视图/系统日志)

**关键函数**:
- `login()` - 用户登录
- `register()` - 用户注册
- `verify_token()` - 验证Token
- `get_products()` - 获取产品列表
- `add_product()` - 添加产品
- `fetch_now()` - 立即采集数据
- `test_connection()` - 测试连接

#### `db.py` - 数据库操作层

**功能**:
- 初始化数据库表
- 提供所有数据库操作函数
- 用户/产品/定时任务/数据/日志 的CRUD

**关键函数**:
- `init_db()` - 初始化数据库表
- `add_user()` - 添加用户
- `get_user_by_username()` - 根据用户名查询用户
- `get_products_by_user()` - 获取某用户的产品列表
- `add_product()` - 添加产品
- `save_daily_data()` - 保存采集数据
- `get_data_by_user_and_date()` - 查询某用户某日的数据

#### `fetch_reports.py` - 数据采集脚本

**功能**:
- 从数据库读取产品配置
- 调用内网API采集数据
- 解析API响应
- 保存数据到数据库

**关键函数**:
- `fetch_for_product(product)` - 采集单个产品的数据
- `fetch_all()` - 采集所有产品的数据
- `main()` - 主函数 (cron调用)

#### `web/login.html` - 登录页面

**功能**:
- 用户登录表单
- 用户注册表单
- Token存储到localStorage

#### `web/index.html` - 主界面

**功能**:
- 数据查询 (按日期/产品)
- 产品管理 (添加/编辑/删除)
- 定时任务管理
- 管理员面板 (用户管理/全局产品视图/系统日志)

---

## 4. 数据库设计

### 4.1 数据库文件

**路径**: `/opt/report-tool/data/app.db`

**引擎**: SQLite 3

### 4.2 表结构

#### 4.2.1 `users` - 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 用户ID |
| `username` | TEXT | UNIQUE NOT NULL | 用户名 |
| `password_hash` | TEXT | NOT NULL | 密码哈希 (SHA256) |
| `is_admin` | INTEGER | DEFAULT 0 | 是否管理员 (0=否, 1=是) |
| `created_at` | TEXT | NOT NULL | 创建时间 (YYYY-MM-DD HH:MM:SS) |

**索引**:
- UNIQUE INDEX on `username`

**示例数据**:
```sql
INSERT INTO users (username, password_hash, is_admin, created_at)
VALUES (
    'admin',
    '239eb129c6d8d5c8855ec4a2a77b03a3a1b57a9c178dc67905880d3d617d1da',  -- admin123
    1,
    '2026-05-28 12:00:00'
);
```

#### 4.2.2 `products` - 产品表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 产品ID |
| `user_id` | INTEGER | NOT NULL | 所属用户ID |
| `name` | TEXT | NOT NULL | 产品名称 |
| `report_type` | TEXT | NOT NULL | 接口类型 (`niunai`/`zhugan`) |
| `pid` | TEXT | NOT NULL | 产品ID (内网API参数) |
| `token` | TEXT | NOT NULL | API Token |
| `channels` | TEXT | - | 渠道列表 (JSON数组字符串) |
| `timezone` | TEXT | DEFAULT 'Etc/GMT+3' | 时区 |
| `account` | TEXT | DEFAULT '' | 账号 (可选) |
| `created_at` | TEXT | NOT NULL | 创建时间 |

**索引**:
- UNIQUE INDEX on (`user_id`, `name`)

**示例数据**:
```sql
INSERT INTO products (user_id, name, report_type, pid, token, channels, timezone, account, created_at)
VALUES (
    1,
    '151102-FB-PWA-24',
    'niunai',
    '15011zcsc',
    'abc123token',
    '["151102-FB-PWA-24"]',
    'Etc/GMT+3',
    '',
    '2026-05-28 12:00:00'
);
```

**说明**:
- `channels` 字段存储JSON数组的字符串形式，如 `'["ch1", "ch2"]'`
- 读取时需要 `json.loads(channels)` 解析
- 写入时需要 `json.dumps(channels_list)` 序列化

#### 4.2.3 `cron_jobs` - 定时任务表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 任务ID |
| `user_id` | INTEGER | NOT NULL | 所属用户ID |
| `cron_expr` | TEXT | NOT NULL | cron表达式 |
| `enabled` | INTEGER | DEFAULT 1 | 是否启用 (0=否, 1=是) |
| `updated_at` | TEXT | NOT NULL | 更新时间 |

**示例数据**:
```sql
INSERT INTO cron_jobs (user_id, cron_expr, enabled, updated_at)
VALUES (
    1,
    '50 0-9,18-23 * * *',  -- 北京时间 00-09点、18-23点的50分执行
    1,
    '2026-05-28 12:00:00'
);
```

#### 4.2.4 `daily_data` - 采集数据表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 数据ID |
| `user_id` | INTEGER | NOT NULL | 所属用户ID |
| `product_id` | INTEGER | NOT NULL | 产品ID |
| `date` | TEXT | NOT NULL | 数据日期 (YYYY-MM-DD) |
| `channel` | TEXT | NOT NULL | 渠道名称 |
| `visit` | INTEGER | DEFAULT 0 | 访问量 |
| `register` | INTEGER | DEFAULT 0 | 注册量 |
| `first_recharge` | INTEGER | DEFAULT 0 | 首充量 |
| `timestamp` | TEXT | NOT NULL | 采集时间戳 |

**索引**:
- UNIQUE INDEX on (`user_id`, `product_id`, `date`, `channel`)

**示例数据**:
```sql
INSERT INTO daily_data (user_id, product_id, date, channel, visit, register, first_recharge, timestamp)
VALUES (
    1,
    1,
    '2026-05-28',
    '151102-FB-PWA-24',
    1000,
    50,
    10,
    '2026-05-28 19:50:00'
);
```

#### 4.2.5 `operation_logs` - 操作日志表 (计划中)

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | 日志ID |
| `user_id` | INTEGER | NOT NULL | 操作用户ID |
| `action` | TEXT | NOT NULL | 操作类型 |
| `detail` | TEXT | - | 操作详情 |
| `created_at` | TEXT | NOT NULL | 操作时间 |

**示例数据**:
```sql
INSERT INTO operation_logs (user_id, action, detail, created_at)
VALUES (
    1,
    'add_product',
    '添加产品: 151102-FB-PWA-24',
    '2026-05-28 12:00:00'
);
```

### 4.3 数据库初始化

**脚本**: `db.init_db()`

**功能**:
- 创建所有表 (如果不存在)
- 创建默认管理员账号 (`admin` / `admin123`)

**执行方式**:
```bash
cd /opt/report-tool
python3 -c "import db; db.init_db()"
```

---

## 5. API接口文档

### 5.1 认证方式

**Token认证**:
- 登录后返回Token，存储到 `localStorage`
- 后续请求在HTTP Header中携带Token:
  ```
  Authorization: Bearer <token>
  ```

**当前简化实现**:
- Token是固定字符串 `'test-token-123'`
- 所有登录用户共享同一个Token
- **生产环境应该用JWT或数据库验证Token**

### 5.2 接口列表

#### 5.2.1 认证接口

##### `POST /api/register` - 用户注册

**请求体**:
```json
{
    "username": "string",
    "password": "string"
}
```

**响应**:
```json
{
    "ok": true,
    "token": "string",
    "user": {
        "id": 1,
        "username": "string",
        "is_admin": 0
    }
}
```

**错误响应**:
```json
{
    "ok": false,
    "error": "用户名已存在"
}
```

##### `POST /api/login` - 用户登录

**请求体**:
```json
{
    "username": "string",
    "password": "string"
}
```

**响应**: 同注册接口

##### `GET /api/user` - 验证Token

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true,
    "user": {
        "id": 1,
        "username": "string",
        "is_admin": 0
    }
}
```

**错误响应** (Token无效):
```json
{
    "ok": false,
    "error": "未登录"
}
```

#### 5.2.2 产品管理接口

##### `GET /api/products` - 获取产品列表

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true,
    "products": [
        {
            "id": 1,
            "user_id": 1,
            "name": "151102-FB-PWA-24",
            "report_type": "niunai",
            "pid": "15011zcsc",
            "token": "abc123",
            "channels": ["151102-FB-PWA-24"],
            "timezone": "Etc/GMT+3",
            "account": "",
            "created_at": "2026-05-28 12:00:00"
        }
    ]
}
```

##### `POST /api/products` - 添加产品

**Headers**:
```
Authorization: Bearer <token>
```

**请求体**:
```json
{
    "name": "string",
    "report_type": "niunai",
    "pid": "string",
    "token": "string",
    "channels": ["string"],
    "timezone": "Etc/GMT+3"
}
```

**响应**:
```json
{
    "ok": true,
    "id": 1
}
```

##### `PUT /api/products/<id>` - 编辑产品

**Headers**:
```
Authorization: Bearer <token>
```

**请求体**: 同添加产品

**响应**:
```json
{
    "ok": true
}
```

##### `DELETE /api/products/<id>` - 删除产品

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true
}
```

##### `POST /api/test-connection` - 测试连接

**Headers**:
```
Authorization: Bearer <token>
```

**请求体**:
```json
{
    "report_type": "niunai",
    "pid": "string",
    "token": "string",
    "channels": ["string"],
    "timezone": "Etc/GMT+3"
}
```

**响应**:
```json
{
    "ok": true,
    "count": 1
}
```

#### 5.2.3 数据采集接口

##### `POST /api/fetch-now` - 立即采集

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true,
    "message": "采集完成"
}
```

#### 5.2.4 数据查询接口

##### `GET /api/data?date=<date>&product_id=<id>` - 查询数据

**Headers**:
```
Authorization: Bearer <token>
```

**参数**:
- `date` (必填): 日期 (YYYY-MM-DD)
- `product_id` (可选): 产品ID (不填则查询所有产品)

**响应**:
```json
{
    "ok": true,
    "data": [
        {
            "id": 1,
            "user_id": 1,
            "product_id": 1,
            "product_name": "151102-FB-PWA-24",
            "date": "2026-05-28",
            "channel": "151102-FB-PWA-24",
            "visit": 1000,
            "register": 50,
            "first_recharge": 10,
            "timestamp": "2026-05-28 19:50:00"
        }
    ]
}
```

#### 5.2.5 管理员接口

> **注意**: 所有管理员接口需要 `is_admin=1` 权限

##### `GET /api/admin/users` - 获取所有用户

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true,
    "users": [
        {
            "id": 1,
            "username": "admin",
            "is_admin": 1,
            "created_at": "2026-05-28 12:00:00"
        }
    ]
}
```

##### `DELETE /api/admin/users/<id>` - 删除用户

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true
}
```

##### `GET /api/admin/products` - 获取所有产品

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true,
    "products": [
        {
            "id": 1,
            "user_id": 1,
            "username": "admin",
            "name": "151102-FB-PWA-24",
            "report_type": "niunai",
            "pid": "15011zcsc",
            "token": "abc123",
            "channels": ["151102-FB-PWA-24"],
            "timezone": "Etc/GMT+3",
            "account": "",
            "created_at": "2026-05-28 12:00:00"
        }
    ]
}
```

##### `GET /api/admin/logs` - 获取系统日志

**Headers**:
```
Authorization: Bearer <token>
```

**响应**:
```json
{
    "ok": true,
    "logs": [
        {
            "id": 1,
            "user_id": 1,
            "username": "admin",
            "action": "add_product",
            "detail": "添加产品: 151102-FB-PWA-24",
            "created_at": "2026-05-28 12:00:00"
        }
    ]
}
```

---

## 6. 前端功能说明

### 6.1 登录页面 (`login.html`)

**路径**: `/login.html`

**功能**:
1. 用户登录表单
   - 用户名输入框
   - 密码输入框
   - "登录"按钮
2. 用户注册表单
   - 用户名输入框
   - 密码输入框
   - "注册"按钮
3. Token管理
   - 登录/注册成功后，Token存储到 `localStorage`
   - 页面跳转到 `/index.html`

**关键代码段**:
```javascript
// 登录
async function login() {
    const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            username: app.username,
            password: app.password
        })
    });
    const data = await res.json();
    if (data.ok) {
        localStorage.setItem('token', data.token);
        window.location.href = '/index.html';
    } else {
        alert(data.error);
    }
}
```

### 6.2 主界面 (`index.html`)

**路径**: `/index.html`

**功能模块**:

#### 6.2.1 顶部导航栏
- 显示当前用户名
- 显示管理员徽章 (如果是管理员)
- "管理员面板"按钮 (仅管理员可见)
- "退出登录"按钮

#### 6.2.2 数据查询卡片
- 日期选择器
- 产品下拉框 (全部产品/指定产品)
- "查询数据"按钮
- "立即采集"按钮
- 数据表格 (日期/产品/渠道/访问/注册/首充/注册率/首充率)

#### 6.2.3 产品管理卡片
- 产品列表 (卡片式展示)
- "添加产品"按钮
- 每个产品卡片包含:
  - 产品名称
  - 接口类型
  - 渠道数
  - 时区
  - "编辑"按钮
  - "删除"按钮
  - "测试连接"按钮

#### 6.2.4 添加/编辑产品模态框
- 查询链接输入框 (粘贴完整URL，自动解析)
- 解析成功后的摘要信息 (接口类型/渠道列表/时区)
- 产品名称输入框 (自动填充第一个渠道名)
- "保存"按钮
- "取消"按钮

**关键代码段**:
```javascript
// 解析产品URL
function parseProductUrl(url) {
    const u = new URL(url);
    const file = u.pathname.split('/').pop() || '';
    
    let report_type = '';
    if (file.includes('zhugan')) {
        report_type = 'zhugan';
    } else if (file.includes('niunai')) {
        report_type = 'niunai';
    } else {
        return null;
    }
    
    const pid = u.searchParams.get('id') || '';
    const token = u.searchParams.get('token') || '';
    const channels = (u.searchParams.get('channels') || '').split(',').filter(c => c);
    const timezone = u.searchParams.get('timezone') || 'Etc/GMT+3';
    
    return { report_type, pid, token, channels, timezone };
}
```

### 6.3 管理员面板

**触发方式**: 点击顶部导航栏的"管理员面板"按钮

**功能模块**:

#### 6.3.1 用户管理
- 用户列表 (ID/用户名/管理员/创建时间)
- "删除"按钮 (删除用户，同时删除其所有产品和数据)

#### 6.3.2 全局产品视图
- 所有用户的产品列表 (用户/产品名称/接口类型/渠道数/创建时间)

#### 6.3.3 系统日志
- 操作日志列表 (时间/用户/操作类型/详情)

---

## 7. 部署指南

### 7.1 服务器配置

**服务器信息**:
- **IP地址**: 150.109.64.37
- **操作系统**: Ubuntu 22.04 LTS
- **SSH用户名**: ubuntu
- **SSH密码**: 1qaz@WSX
- **项目目录**: `/opt/report-tool/`

**SSH连接**:
```bash
ssh ubuntu@150.109.64.37
# 输入密码: 1qaz@WSX
```

**重要**: 腾讯云Ubuntu默认禁用密码登录，需要手动启用:
1. 修改 `/etc/ssh/sshd_config`:
   ```
   PasswordAuthentication yes
   ```
2. 重启SSH服务:
   ```bash
   sudo systemctl restart sshd
   ```

### 7.2 部署步骤

#### 7.2.1 首次部署

**步骤**:
1. 购买腾讯云轻量应用服务器 (香港/Ubuntu 22.04/2核2G)
2. 启用SSH密码登录 (见上文)
3. 创建项目目录:
   ```bash
   sudo mkdir -p /opt/report-tool
   sudo chown ubuntu:ubuntu /opt/report-tool
   ```
4. 上传文件 (从本地Mac):
   ```bash
   cd ~/WorkBuddy/data
   expect -c "
   spawn scp -o StrictHostKeyChecking=no server.py api.py db.py fetch_reports.py ubuntu@150.109.64.37:/opt/report-tool/
   expect \"password:\"
   send \"1qaz@WSX\r\"
   expect eof
   "
   ```
5. 初始化数据库:
   ```bash
   ssh ubuntu@150.109.64.37
   cd /opt/report-tool
   python3 -c "import db; db.init_db()"
   ```
6. 启动服务:
   ```bash
   cd /opt/report-tool
   nohup python3 server.py > logs/app.log 2>&1 &
   ```
7. 访问应用:
   - 登录页面: http://150.109.64.37:8991/login.html
   - 主界面: http://150.109.64.37:8991/index.html

#### 7.2.2 更新部署

**步骤**:
1. 本地修改代码
2. 上传修改后的文件:
   ```bash
   cd ~/WorkBuddy/data
   expect -c "
   spawn scp -o StrictHostKeyChecking=no server.py api.py db.py fetch_reports.py web/login.html web/index.html ubuntu@150.109.64.37:/opt/report-tool/
   expect \"password:\"
   send \"1qaz@WSX\r\"
   expect eof
   "
   ```
3. 重启服务:
   ```bash
   ssh ubuntu@150.109.64.37
   cd /opt/report-tool
   pkill -f "python3 server.py"
   nohup python3 server.py > logs/app.log 2>&1 &
   ```

### 7.3 systemd服务配置 (推荐)

**创建服务文件** `/etc/systemd/system/report-tool.service`:
```ini
[Unit]
Description=Report Tool Web Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/report-tool
ExecStart=/usr/bin/python3 /opt/report-tool/server.py
Restart=always
RestartSec=10
StandardOutput=append:/opt/report-tool/logs/app.log
StandardError=append:/opt/report-tool/logs/app.log

[Install]
WantedBy=multi-user.target
```

**启用服务**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable report-tool
sudo systemctl start report-tool
sudo systemctl status report-tool
```

**查看日志**:
```bash
sudo journalctl -u report-tool -f
```

### 7.4 cron定时任务配置

**当前配置** (单用户版):
```bash
# 编辑crontab
crontab -e

# 添加以下行
50 0-9,18-23 * * * /bin/bash /opt/report-tool/fetch_cron.sh
```

**多用户版** (计划使用APScheduler):
- 不使用系统cron
- 在 `server.py` 中集成APScheduler
- 每个用户独立管理自己的定时任务

---

## 8. 开发指南

### 8.1 本地环境搭建

**步骤**:
1. 安装Python 3.9+:
   ```bash
   python3 --version
   ```
2. 克隆代码 (如果是Git仓库):
   ```bash
   git clone <repo-url> ~/WorkBuddy/data/
   ```
3. 创建虚拟环境 (可选但推荐):
   ```bash
   cd ~/WorkBuddy/data
   python3 -m venv venv
   source venv/bin/activate
   ```
4. 安装依赖:
   ```bash
   pip install flask requests apscheduler
   ```
5. 初始化数据库:
   ```bash
   python3 -c "import db; db.init_db()"
   ```
6. 启动服务:
   ```bash
   python3 server.py
   ```
7. 访问应用:
   - 登录页面: <html><body><p> <a href="http://localhost:8991/login.html">http://localhost:8991/login.html</a></p></body></html>
   - 主界面: <html><body><p> <a href="http://localhost:8991/index.html">http://localhost:8991/index.html</a></p></body></html>

### 8.2 代码规范

**Python代码规范**:
- 遵循PEP 8
- 使用4空格缩进
- 函数名使用小写+下划线 (`snake_case`)
- 类名使用首字母大写 (`PascalCase`)
- 常量使用大写+下划线 (`UPPER_CASE`)

**JavaScript代码规范**:
- 使用2空格缩进
- 变量名使用驼峰命名 (`camelCase`)
- 常量使用大写+下划线 (`UPPER_CASE`)
- 使用Vue 3 Composition API (如果复杂组件)

**数据库操作规范**:
- 所有数据库操作封装在 `db.py` 中
- 使用参数化查询防止SQL注入
- 每次操作后关闭数据库连接

**API接口规范**:
- 所有响应都是JSON格式
- 成功响应: `{"ok": true, ...}`
- 失败响应: `{"ok": false, "error": "..."}`
- HTTP状态码: 200 (成功), 400 (参数错误), 401 (未登录), 500 (服务器错误)

### 8.3 调试技巧

**后端调试**:
- 查看Flask日志:
  ```bash
  tail -f /opt/report-tool/logs/app.log
  ```
- 使用 `print()` 或 `logging` 模块输出调试信息
- 使用Python调试器:
  ```python
  import pdb; pdb.set_trace()
  ```

**前端调试**:
- 使用浏览器开发者工具 (F12)
- 查看Console标签页的JavaScript错误
- 查看Network标签页的API请求/响应
- 使用 `console.log()` 输出调试信息

**数据库调试**:
- 使用SQLite命令行工具:
  ```bash
  sqlite3 /opt/report-tool/data/app.db
  .tables
  .schema users
  SELECT * FROM users;
  .quit
  ```

---

## 9. 待完成任务清单

### 9.1 高优先级 (必须完成)

| 任务 | 说明 | 负责文件 | 状态 |
|------|------|----------|------|
| **修复api.py语法错误** | 3处缺少逗号 | `api.py` | ❌ 未开始 |
| **测试多用户版部署** | 上传文件到服务器，测试所有功能 | 所有 | ❌ 未开始 |
| **实现Token验证** | 当前Token是固定的，需要改成JWT或数据库验证 | `server.py`, `api.py` | ❌ 未开始 |
| **集成APScheduler** | 在 `server.py` 中集成APScheduler，替代系统cron | `server.py` | ❌ 未开始 |

### 9.2 中优先级 (应该完成)

| 任务 | 说明 | 负责文件 | 状态 |
|------|------|----------|------|
| **添加操作日志** | 在 `operation_logs` 表中记录所有关键操作 | `api.py`, `db.py` | ❌ 未开始 |
| **数据导出功能** | 添加CSV/Excel导出按钮 | `index.html`, `api.py` | ❌ 未开始 |
| **优化数据查询UI** | 添加图表展示 (折线图/柱状图) | `index.html` | ❌ 未开始 |
| **添加数据清理功能** | 用户可以手动清理旧数据 | `index.html`, `api.py`, `db.py` | ❌ 未开始 |

### 9.3 低优先级 (可选完成)

| 任务 | 说明 | 负责文件 | 状态 |
|------|------|----------|------|
| **使用Gunicorn** | 替换Flask内置服务器，提升性能 | `server.py` | ❌ 未开始 |
| **添加HTTPS** | 使用Let's Encrypt免费证书 | 服务器配置 | ❌ 未开始 |
| **添加单元测试** | 为关键函数添加单元测试 | `test_*.py` | ❌ 未开始 |
| **容器化部署** | 使用Docker容器化应用 | `Dockerfile`, `docker-compose.yml` | ❌ 未开始 |

---

## 10. 常见问题排查

### 10.1 SSH连接失败

**症状**: `Permission denied (publickey)`

**原因**: 腾讯云Ubuntu默认禁用密码登录

**解决方案**:
1. 通过腾讯云控制台WebShell登录
2. 修改 `/etc/ssh/sshd_config`:
   ```
   PasswordAuthentication yes
   ```
3. 重启SSH服务:
   ```bash
   sudo systemctl restart sshd
   ```

### 10.2 数据库初始化失败

**症状**: `AttributeError: module 'db' has no attribute 'init_db'`

**原因**: `db.py` 中没有 `init_db()` 函数，或者文件上传不完整

**解决方案**:
1. 检查 `db.py` 是否有 `init_db()` 函数
2. 重新上传 `db.py` 到服务器
3. 再次执行初始化命令

### 10.3 内网API无法访问

**症状**: 测试连接失败，`requests.exceptions.ConnectionError`

**原因**: 服务器无法访问内网地址 `16.163.114.99:8990`

**解决方案**:
1. 在服务器上测试连通性:
   ```bash
   curl "http://16.163.114.99:8990/reportniunai.php?id=...&token=...&channels=...&timezone=..."
   ```
2. 如果无法访问，联系网络管理员开通权限

### 10.4 Token验证失败

**症状**: 所有API请求返回 `{"ok": false, "error": "未登录"}`

**原因**: Token存储/传递有问题

**解决方案**:
1. 检查浏览器 `localStorage` 中是否有 `token`
2. 检查HTTP请求Header中是否携带 `Authorization: Bearer <token>`
3. 检查 `server.py` 中的Token验证逻辑

### 10.5 数据表格不显示

**症状**: 点击"查询数据"后，表格显示"请选择日期并点击查询数据"

**原因**: 没有数据，或者日期选择错误

**解决方案**:
1. 先点击"立即采集"按钮采集数据
2. 选择有数据的日期
3. 检查浏览器Console标签页是否有JavaScript错误

### 10.6 产品解析失败

**症状**: 粘贴查询链接后，没有自动解析

**原因**: URL格式错误，或者接口类型不支持

**解决方案**:
1. 检查URL是否完整 (包含 `http://`)
2. 检查URL路径是否包含 `reportniunai.php` 或 `reportzhugan.php`
3. 检查URL参数是否包含 `id`, `token`, `channels`, `timezone`

---

## 11. 快速上手检查清单

### 11.1 接手项目前的准备

- [ ] 阅读本文档的完整内容
- [ ] 了解项目背景和核心功能
- [ ] 了解技术栈 (Python/Flask/SQLite/Vue3/Tailwind)
- [ ] 了解数据库表结构
- [ ] 了解API接口列表

### 11.2 首次部署步骤

- [ ] 购买腾讯云轻量应用服务器 (如果没有)
- [ ] 启用SSH密码登录
- [ ] 上传代码到服务器
- [ ] 初始化数据库
- [ ] 启动服务
- [ ] 访问登录页面测试

### 11.3 日常开发流程

- [ ] 本地修改代码
- [ ] 本地测试
- [ ] 上传到服务器
- [ ] 重启服务
- [ ] 线上测试

### 11.4 Bug修复流程

- [ ] 复现Bug
- [ ] 定位问题 (后端/前端/数据库)
- [ ] 修复代码
- [ ] 本地测试
- [ ] 上传到服务器
- [ ] 重启服务
- [ ] 线上验证

---

## 12. 联系方式

**项目负责人**:  mx

**AI助手**: WorkBuddy (可随时接管项目)

**服务器IP**: 150.109.64.37

**登录地址**: <html><body><p> <a href="http://150.109.64.37:8991/login.html">http://150.109.64.37:8991/login.html</a></p></body></html>

**管理员账号**: admin / admin123

---

## 13. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-20 | 单用户版，pywebview桌面应用 |
| v1.1 | 2026-05-22 | 改为Web应用，部署到云服务器 |
| v2.0 | 2026-05-28 | 多用户改造 (进行中) |

---

## 14. 附录

### 14.1 内网API接口说明

**接口1: reportniunai.php** (用于G45, 82B产品)

**URL**: `http://16.163.114.99:8990/reportniunai.php`

**参数**:
- `id`: 产品ID (如 `15011zcsc`)
- `token`: API Token
- `channels`: 渠道列表 (逗号分隔, 如 `ch1,ch2`)
- `timezone`: 时区 (如 `Etc/GMT+3`)
- `date`: 日期 (可选, 格式 `YYYY-MM-DD`, 默认昨天)

**响应示例**:
```json
{
    "code": 0,
    "msg": "success",
    "data": [
        {
            "date": "2026-05-27",
            "channel": "151102-FB-PWA-24",
            "visit": 1000,
            "register": 50,
            "first_recharge": 10
        }
    ]
}
```

**接口2: reportzhugan.php** (用于35X产品)

**URL**: `http://16.163.114.99:8990/reportzhugan.php`

**参数**: 同 reportniunai.php

**响应**: 同 reportniunai.php

### 14.2 产品链接格式说明

**完整URL格式**:
```
http://16.163.114.99:8990/<接口文件>?id=<产品ID>&token=<Token>&channels=<渠道列表>&timezone=<时区>
```

**示例**:
```
http://16.163.114.99:8990/reportniunai.php?id=15011zcsc&token=abc123&channels=151102-FB-PWA-24&timezone=Etc/GMT+3
```

### 14.3 时区说明

**巴西时区**: `Etc/GMT+3` (比UTC晚3小时，即UTC-3)

**北京时间**: UTC+8

**转换关系**:
- 巴西时间 = 北京时间 - 11小时
- 例如: 北京时间 2026-05-28 12:00:00 → 巴西时间 2026-05-28 01:00:00

---

**文档结束**

> 如果你接手了这个项目，请先阅读本文档的完整内容，理解项目的架构和代码逻辑，然后再开始修改代码。  
> 如果遇到问题，请先查看"常见问题排查"章节，如果还无法解决，再联系项目负责人。  
> 祝你工作顺利！🚀
