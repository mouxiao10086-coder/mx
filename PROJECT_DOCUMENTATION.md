# 甲方后台定时查询工具 - 完整技术文档

> **文档版本**: v2.0  
> **更新时间**: 2026-05-28  
> **项目状态**: 多用户版开发中（单用户版已部署）  
> **目标读者**: AI模型、新开发者、运维人员

---

## 📋 项目概述

### 项目背景
巴西真金游戏（Slots）广告投放团队需要定时从内网报表API采集产品数据（访问/注册/首充），用于广告效果分析。初始版本为pywebview桌面应用，现改为Web应用支持多用户远程访问。

### 核心功能
1. **产品管理**: 添加/编辑/删除产品，支持URL自动解析
2. **数据查询**: 按日期/产品查看采集数据
3. **定时采集**: 支持cron表达式配置采集时间
4. **多用户隔离**: 每个用户只能看到自己的产品和采集数据（开发中）
5. **管理员视图**: 管理员可查看所有用户数据（开发中）

### 技术架构
```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                          │
│                  (Web UI - index.html)                    │
└──────────────────────┬────────────────────────────────────┘
                       │ HTTP (端口 8991)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Flask应用服务器 (server.py)                    │
│  - 静态文件服务 (web/)                                     │
│  - 登录认证 (login.html + Token验证)                       │
│  - API路由转发 → api.py                                    │
└──────────────────────┬────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                API业务逻辑层 (api.py)                       │
│  - 用户认证 (login/verify_token)                           │
│  - 产品管理 (CRUD + URL解析)                              │
│  - 数据查询 (按日期/产品/渠道)                            │
│  - 定时任务管理 (cron配置)                                 │
└──────────────────────┬────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              数据访问层 (db.py - 开发中)                    │
│  - SQLite数据库操作 (app.db)                               │
│  - 用户表/产品表/任务表/数据表                            │
└──────────────────────┬────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              定时采集脚本 (fetch_reports.py)              │
│  - 调用内网API (16.163.114.99:8990)                    │
│  - 解析JSON响应                                            │
│  - 存储到数据库                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ 技术栈

### 后端
- **Python 3.13.12** (推荐) / 3.9.6 (兼容)
- **Flask** - Web框架 (server.py提供HTTP服务)
- **SQLite 3** - 数据库 (单文件，无需单独服务)
- **APScheduler** - Python定时任务调度器 (多用户版使用)
- **pywebview** - 桌面应用封装 (已弃用，改用Web版)

### 前端
- **原生HTML/CSS/JavaScript** (无框架)
- **Tailwind CSS** (CDN引入) - UI样式
- **Vue 3** (CDN引入) - 响应式数据绑定
- **Chart.js** (CDN引入) - 图表展示 (预留)

### 部署
- **腾讯云轻量应用服务器**
  - IP: `150.109.64.0`
  - 地域: 香港
  - 系统: Ubuntu 22.04 LTS
  - 配置: 2核2G
- **systemd** - Linux服务管理
- **cron** - 系统级定时任务 (单用户版使用)

---

## 📂 项目结构

```
/opt/report-tool/           # 服务器部署目录
├── server.py               # HTTP服务入口 (端口8991)
├── api.py                  # API业务逻辑 (单用户版)
├── api_multiusr.py         # API业务逻辑 (多用户版 - 开发中)
├── fetch_reports.py        # 数据采集脚本
├── fetch_cron.sh           # cron执行脚本
├── db.py                   # 数据库操作层 (多用户版)
├── data/
│   ├── app.db              # SQLite数据库 (多用户版)
│   ├── app_config.json     # 应用配置 (数据存储路径等)
│   ├── products_config.json # 产品配置 (单用户版)
│   └── daily/
│       ├── YYYY-MM-DD.json # 每日采集数据 (单用户版)
│       └── fetch.log       # 采集日志
├── web/
│   ├── index.html          # 主界面 (Vue 3 + Tailwind)
│   ├── login.html          # 登录页面 (多用户版)
│   └── css/
│       └── style.css       # 自定义样式 (预留)
├── logs/
│   └── app.log             # 应用日志
└── systemd/
    └── report-tool.service # systemd服务配置

本地开发目录:
~/WorkBuddy/data/          # 源代码目录
├── server.py
├── api.py
├── fetch_reports.py
├── db.py                   # 新增：数据库层
├── web/
│   └── index.html
└── PROJECT_DOCUMENTATION.md  # 本文档
```

---

## 🗄️ 数据库设计 (多用户版)

### SQLite数据库: `/opt/report-tool/data/app.db`

#### 表1: users (用户表)
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,  -- 0=普通用户, 1=管理员
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 初始账号
-- 管理员: admin / admin123
-- 普通用户: user1 / user1123
```

#### 表2: products (产品表)
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,  -- 'niunai' or 'zhugan'
    pid TEXT NOT NULL,           -- 产品ID (URL参数id)
    token TEXT NOT NULL,         -- 认证令牌 (URL参数token)
    channels TEXT NOT NULL,      -- 渠道列表 (JSON array)
    timezone TEXT DEFAULT 'Etc/GMT+3',  -- 时区 (巴西)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name),       -- 同一用户不能创建同名产品
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### 表3: cron_jobs (定时任务表)
```sql
CREATE TABLE cron_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    cron_expr TEXT NOT NULL,     -- cron表达式 (如 "50 0-9,18-23 * * *")
    enabled INTEGER DEFAULT 1,   -- 0=禁用, 1=启用
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### 表4: daily_data (采集数据表)
```sql
CREATE TABLE daily_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    date TEXT NOT NULL,          -- YYYY-MM-DD格式
    channel TEXT NOT NULL,        -- 渠道标识 (如 "151102-FB-PWA-24")
    visit INTEGER DEFAULT 0,     -- 访问量
    register INTEGER DEFAULT 0,   -- 注册量
    first_recharge INTEGER DEFAULT 0,  -- 首充量
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, product_id, date, channel),  -- 防止重复插入
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

#### 表5: operation_logs (操作日志表 - 可选)
```sql
CREATE TABLE operation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,        -- 'login', 'add_product', 'delete_product', etc.
    details TEXT,                -- JSON格式的详细信息
    ip_address TEXT,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🔌 API接口文档

### 认证相关

#### 1. 用户登录
```
POST /api/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}

Response:
{
  "success": true,
  "token": "eyJ0eXAiOiJKV1QiLCJhbG...",
  "user": {
    "id": 1,
    "username": "admin",
    "is_admin": 1
  }
}
```

#### 2. 验证Token
```
GET /api/verify_token
Headers:
  Authorization: Bearer {token}

Response:
{
  "success": true,
  "user": {...}
}
```

#### 3. 用户注册 (管理员可用)
```
POST /api/register
Headers:
  Authorization: Bearer {admin_token}
Content-Type: application/json

{
  "username": "newuser",
  "password": "password123",
  "is_admin": 0
}
```

### 产品管理

#### 4. 获取产品列表
```
GET /api/products
Headers:
  Authorization: Bearer {token}

Response:
{
  "success": true,
  "products": [
    {
      "id": 1,
      "name": "G45",
      "report_type": "niunai",
      "pid": "15011zcsc",
      "token": "abc123...",
      "channels": ["151102-FB-PWA-24"],
      "timezone": "Etc/GMT+3"
    }
  ]
}
```

#### 5. 添加产品
```
POST /api/products
Headers:
  Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "G45",
  "url": "http://16.163.114.99:8990/reportniunai.php?id=15011zcsc&token=xxx&channels=151102-FB-PWA-24&timezone=Etc/GMT+3"
}

Response:
{
  "success": true,
  "product": {...}
}
```

#### 6. 更新产品
```
PUT /api/products/{product_id}
Headers:
  Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "G45-new",
  "channels": ["151102-FB-PWA-24", "151103-FB-PWA-25"]
}
```

#### 7. 删除产品
```
DELETE /api/products/{product_id}
Headers:
  Authorization: Bearer {token}

Response:
{
  "success": true
}
```

### 数据查询

#### 8. 查询采集数据
```
GET /api/data?date=2026-05-28&product_id=1
Headers:
  Authorization: Bearer {token}

Response:
{
  "success": true,
  "data": [
    {
      "date": "2026-05-28",
      "channel": "151102-FB-PWA-24",
      "visit": 1234,
      "register": 56,
      "first_recharge": 12
    }
  ]
}
```

#### 9. 手动触发采集
```
POST /api/fetch
Headers:
  Authorization: Bearer {token}
Content-Type: application/json

{
  "product_id": 1,
  "date": "2026-05-28"  // 可选，默认今天
}

Response:
{
  "success": true,
  "message": "采集完成"
}
```

### 定时任务管理

#### 10. 获取定时任务配置
```
GET /api/cron
Headers:
  Authorization: Bearer {token}

Response:
{
  "success": true,
  "cron_expr": "50 0-9,18-23 * * *",
  "enabled": 1
}
```

#### 11. 更新定时任务
```
PUT /api/cron
Headers:
  Authorization: Bearer {token}
Content-Type: application/json

{
  "cron_expr": "50 0-9,18-23 * * *",
  "enabled": 1
}
```

### 管理员接口

#### 12. 获取所有用户 (管理员)
```
GET /api/admin/users
Headers:
  Authorization: Bearer {admin_token}

Response:
{
  "success": true,
  "users": [...]
}
```

#### 13. 获取所有产品 (管理员)
```
GET /api/admin/products
Headers:
  Authorization: Bearer {admin_token}

Response:
{
  "success": true,
  "products": [...]
}
```

---

## 🎨 前端功能说明

### 页面结构

#### 1. 登录页面 (`login.html`)
- **布局**: 居中卡片式设计
- **功能**:
  - 用户名/密码输入
  - "记住我"选项 (localStorage保存token)
  - 登录失败提示
  - 注册入口 (管理员可开启)

#### 2. 主界面 (`index.html`)
- **顶部导航栏**:
  - 左侧: Logo + 项目名
  - 右侧: 用户信息 + 退出按钮

- **侧边栏菜单**:
  - 📊 数据查询 (默认页)
  - ⚙️ 产品管理
  - ⏰ 定时任务 (普通用户)
  - 👥 用户管理 (管理员)
  - 📝 操作日志 (管理员)

- **数据查询页**:
  - 日期选择器 (默认今天)
  - 产品下拉列表 (仅当前用户的产品)
  - 渠道多选 (checkbox)
  - 数据表格 (访问/注册/首充)
  - 趋势图表 (Chart.js)

- **产品管理页**:
  - 产品列表 (卡片式展示)
  - "添加产品"按钮 → 弹窗
    - 字段1: 查询链接 (粘贴自动解析)
    - 字段2: 产品名称 (默认用第一个渠道名)
    - 只读摘要: 接口类型/渠道列表/时区
  - "测试连接"按钮
  - "删除"按钮 (二次确认)

- **定时任务页**:
  - cron表达式输入框
  - 启用/禁用开关
  - 下次执行时间预览
  - "保存"按钮

---

## 🚀 部署指南

### 前置条件
1. **腾讯云服务器** (已购买)
   - IP: `150.109.64.0`
   - 用户: `ubuntu`
   - 密码: `1qaz@WSX`

2. **SSH访问配置**
   ```bash
   # 如果无法密码登录，通过腾讯云WebShell执行：
   sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
   sudo systemctl restart sshd
   ```

### 部署步骤

#### 方式1: 使用部署脚本 (推荐)
```bash
# 在本地Mac执行
cd ~/WorkBuddy/data/
chmod +x deploy.sh
./deploy.sh
```

#### 方式2: 手动部署
```bash
# 1. 上传文件到服务器
expect -c "
spawn scp -o StrictHostKeyChecking=no server.py ubuntu@150.109.64.0:/opt/report-tool/
expect \"password:\"
send \"1qaz@WSX\r\"
expect eof
"

# 2. SSH到服务器
ssh ubuntu@150.109.64.0

# 3. 安装依赖
cd /opt/report-tool/
python3 -m venv venv
source venv/bin/activate
pip install flask apscheduler

# 4. 初始化数据库 (多用户版)
python3 db.py

# 5. 启动systemd服务
sudo systemctl daemon-reload
sudo systemctl enable report-tool
sudo systemctl start report-tool

# 6. 检查状态
sudo systemctl status report-tool
curl <a href="http://localhost:8991/api/health">http://localhost:8991/api/health</a>
```

#### 方式3: 使用Ansible (适合批量部署)
```yaml
# playbook.yml (待编写)
- hosts: report_servers
  tasks:
    - name: 上传应用文件
      copy: src=files/ dest=/opt/report-tool/
    - name: 安装依赖
      pip: requirements=requirements.txt
    - name: 启动服务
      systemd: name=report-tool state=started enabled=yes
```

### 验证部署
```bash
# 1. 检查服务状态
ssh ubuntu@150.109.64.0 "sudo systemctl status report-tool"

# 2. 测试API
curl <a href="http://150.109.64.0:8991/api/health">http://150.109.64.0:8991/api/health</a>

# 3. 测试登录
curl -X POST <a href="http://150.109.64.0:8991/api/login">http://150.109.64.0:8991/api/login</a> \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 4. 浏览器访问
open <a href="http://150.109.64.0:8991/">http://150.109.64.0:8991/</a>
```

---

## 💻 开发指南

### 本地开发环境搭建

#### 1. 克隆代码
```bash
cd ~/WorkBuddy/data/
# 已有源代码
```

#### 2. 创建虚拟环境
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask apscheduler
```

#### 3. 启动开发服务器
```bash
# 单用户版
python3 server.py

# 多用户版 (开发中)
python3 server_multiusr.py
```

#### 4. 访问应用
```
<a href="http://localhost:8991/">http://localhost:8991/</a>
```

### 代码规范

#### Python代码风格
```python
# 1. 使用类型注解
def get_products(user_id: int) -> List[Dict]:
    pass

# 2. 错误处理
try:
    result = fetch_report(product)
except requests.RequestException as e:
    logger.error(f"采集失败: {e}")
    return None

# 3. 配置分离
import os
DATABASE = os.getenv('DATABASE', 'data/app.db')
```

#### JavaScript代码风格
```javascript
// 1. 使用ES6+语法
const parseProductUrl = (url) => {
  const u = new URL(url.trim());
  return {...};
};

// 2. 异步请求封装
const apiRequest = async (endpoint, options = {}) => {
  const token = localStorage.getItem('token');
  const response = await fetch(endpoint, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  return response.json();
};

// 3. 模块化组织
// utils.js - 工具函数
// api.js - API调用封装
// components.js - Vue组件
```

### 调试技巧

#### 后端调试
```bash
# 1. 查看应用日志
ssh ubuntu@150.109.64.0 "tail -f /opt/report-tool/logs/app.log"

# 2. 手动测试API
curl -X GET <a href="http://150.109.64.0:8991/api/products">http://150.109.64.0:8991/api/products</a>

# 3. Python调试器
import pdb; pdb.set_trace()
```

#### 前端调试
```javascript
// 1. 浏览器开发者工具 (F12)
//   - Console: 查看JS错误
//   - Network: 查看API请求
//   - Application: 查看localStorage

// 2. Vue Devtools (Chrome扩展)
//   - 查看组件状态
//   - 调试数据绑定

// 3. 添加调试日志
console.log('产品数据:', this.products);
```

---

## 🐛 常见问题排查

### 问题1: SSH无法密码登录
**症状**: `Permission denied (publickey)`

**原因**: 腾讯云默认禁用密码登录

**解决**:
```bash
# 通过腾讯云WebShell执行：
sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart sshd
```

### 问题2: 服务启动失败
**症状**: `systemctl status report-tool` 显示 `failed`

**排查**:
```bash
# 查看详细日志
sudo journalctl -u report-tool -n 50

# 常见原因：
# 1. Python路径错误 → 修改service文件的ExecStart
# 2. 端口被占用 → netstat -tuln | grep 8991
# 3. 数据库文件权限 → chown ubuntu:ubuntu data/app.db
```

### 问题3: 采集失败 (内网API不可达)
**症状**: 点击"立即采集"无响应

**排查**:
```bash
# 1. 测试内网连通性
ssh ubuntu@150.109.64.0 "curl -I <a href="http://16.163.114.99:8990/">http://16.163.114.99:8990/</a>"

# 2. 检查产品配置
cat /opt/report-tool/data/products_config.json

# 3. 手动执行采集脚本
python3 /opt/report-tool/fetch_reports.py --product G45 --date 2026-05-28
```

### 问题4: 数据库锁定 (SQLite)
**症状**: `database is locked`

**原因**: 多个进程同时写入SQLite

**解决**:
```python
# 1. 使用WAL模式 (db.py)
conn.execute("PRAGMA journal_mode=WAL")

# 2. 添加重试逻辑
import time
for i in range(3):
    try:
        conn.commit()
        break
    except sqlite3.OperationalError:
        time.sleep(0.1)
```

### 问题5: 前端无法访问API (CORS)
**症状**: `No 'Access-Control-Allow-Origin' header`

**解决**:
```python
# server.py 添加CORS支持
from flask_cors import CORS
CORS(app)
```

### 问题6: Token验证失败
**症状**: API返回 `{"success": false, "error": "Invalid token"}`

**排查**:
```javascript
// 1. 检查localStorage
console.log(localStorage.getItem('token'));

// 2. 检查Token过期时间
const payload = JSON.parse(atob(token.split('.')[1]));
console.log('过期时间:', new Date(payload.exp * 1000));

// 3. 重新登录获取新Token
await apiRequest('/api/login', {...});
```

---

## 📝 待完成任务清单

### 高优先级 (本周完成)
- [ ] 完成 `api_multiusr.py` 重写 (登录+Token验证+user_id过滤)
- [ ] 测试多用户隔离逻辑 (用户A不能看到用户B的产品)
- [ ] 完成 `server_multiusr.py` (集成APScheduler)
- [ ] 编写部署脚本 `deploy_multiusr.sh`
- [ ] 更新 `systemd` 服务配置

### 中优先级 (本月完成)
- [ ] 实现管理员视图 (用户管理+产品管理)
- [ ] 添加操作日志功能
- [ ] 优化前端UI (响应式布局)
- [ ] 添加数据导出功能 (CSV/Excel)
- [ ] 实现数据采集失败重试机制

### 低优先级 (未来优化)
- [ ] 支持更多报表API端点
- [ ] 添加数据可视化图表 (Chart.js)
- [ ] 实现邮件/微信通知 (采集失败告警)
- [ ] 支持Docker容器化部署
- [ ] 编写自动化测试 (pytest + Jest)

---

## 🔐 安全注意事项

### 1. 密码存储
```python
# 使用bcrypt哈希密码 (不要明文存储)
import bcrypt
password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
```

### 2. Token生成
```python
# 使用JWT (JSON Web Token)
import jwt
token = jwt.encode({'user_id': user_id, 'exp': exp}, SECRET_KEY, algorithm='HS256')
```

### 3. SQL注入防护
```python
# 使用参数化查询 (不要拼接SQL)
cursor.execute("SELECT * FROM products WHERE user_id = ?", (user_id,))
# ❌ 错误示例
cursor.execute(f"SELECT * FROM products WHERE user_id = {user_id}")
```

### 4. XSS防护
```javascript
// Vue自动转义HTML (使用v-text或{{ }}插值)
<div>{{ userInput }}</div>
// ❌ 危险操作
<div v-html="userInput"></div>
```

### 5. HTTPS部署 (生产环境)
```bash
# 使用Let's Encrypt免费证书
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d report-tool.example.com
```

---

## 📊 性能优化建议

### 1. 数据库优化
```sql
-- 添加索引
CREATE INDEX idx_daily_data_user_date ON daily_data(user_id, date);
CREATE INDEX idx_products_user ON products(user_id);

-- 定期VACUUM (释放空间)
VACUUM;
```

### 2. API缓存
```python
from flask_caching import Cache
cache = Cache(config={'CACHE_TYPE': 'simple'})

@cache.cached(timeout=300)  # 缓存5分钟
def get_products(user_id):
    return query_products(user_id)
```

### 3. 前端懒加载
```javascript
// 按需加载图表库
const Chart = () => import('chart.js/auto');
```

---

## 📞 联系方式

**项目负责人**:  mx  
**邮箱**: [待补充]  
**企业微信**: [待补充]  

**GitHub仓库**: [待创建]  
**腾讯云控制台**: https://console.cloud.tencent.com/lighthouse/instance  

---

## 📜 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-05-20 | 初始版本 (pywebview桌面应用) |
| v1.1 | 2026-05-22 | 改为Web应用，部署到腾讯云 |
| v1.2 | 2026-05-25 | 产品添加支持URL自动解析 |
| v2.0 | 2026-05-28 | 多用户版开发启动 |
| v2.1 | [待发布] | 多用户版上线，管理员视图 |

---

## 🎯 快速上手检查清单

如果你是第一次接手这个项目，按以下步骤操作：

- [ ] 1. 阅读本文档的"项目概述"和"技术架构"部分
- [ ] 2. 搭建本地开发环境 (参见"开发指南")
- [ ] 3. SSH连接到服务器，查看当前部署状态
- [ ] 4. 阅读 `api.py` 和 `index.html` 理解现有逻辑
- [ ] 5. 阅读 `db.py` 了解数据库设计
- [ ] 6. 运行单元测试 (待编写)
- [ ] 7. 尝试修改一个小功能 (如修改页面标题)
- [ ] 8. 提交代码并部署到测试环境
- [ ] 9. 通知项目负责人 code review

---

**文档结束** | 如有疑问，请联系项目负责人或在GitHub提Issue
