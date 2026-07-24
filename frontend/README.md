# AI面试陪练 - 前端项目

## 项目简介

AI面试陪练系统前端，基于 React + Vite 构建，提供简历管理、岗位匹配、模拟面试等功能的用户界面。

## 技术栈

- **框架**: React 18
- **构建工具**: Vite 5
- **路由**: react-router-dom v6
- **图表**: recharts
- **样式**: 纯 CSS（使用 CSS Variables 主题系统）

## 目录结构

```
frontend/
├── index.html              # HTML 入口
├── package.json            # 依赖配置
├── vite.config.js          # Vite 配置（含 API 代理）
├── src/
│   ├── main.jsx            # React 入口
│   ├── App.jsx             # 路由配置
│   ├── styles.css          # 全局样式
│   ├── api/
│   │   └── client.js       # API 客户端（含 Mock 数据降级）
│   ├── contexts/
│   │   └── AuthContext.jsx # 认证状态管理
│   ├── components/
│   │   ├── Layout.jsx      # 主布局（侧边栏+顶栏）
│   │   └── ProtectedRoute.jsx
│   └── pages/
│       ├── Dashboard.jsx         # 数据看板（6张图表）
│       ├── Login.jsx             # 用户登录
│       ├── Register.jsx          # 用户注册
│       ├── ResumeUpload.jsx      # 简历上传和版本管理
│       ├── ResumeReview.jsx      # 简历审核结果
│       ├── JobCollection.jsx     # 岗位采集和批量导入
│       ├── JobReview.jsx         # 岗位审核管理
│       ├── JobSearchMatch.jsx    # 岗位搜索和匹配
│       ├── JobComparison.jsx     # 多岗位横向对比
│       ├── MockInterview.jsx     # 模拟面试对话
│       ├── InterviewHistory.jsx  # 面试记录和报告
│       └── ErrorPage.jsx         # 异常提示页面(404/500/Agent)
├── tests/
│   └── manual-test-checklist.js  # 手动测试清单
└── dist/                   # 构建产物
```

## 功能页面（共11页）

| 序号 | 页面 | 路由 | 说明 |
|------|------|------|------|
| 1 | 用户登录 | `/login` | 登录表单，含表单校验和演示账号提示 |
| 2 | 用户注册 | `/register` | 注册表单，含密码确认校验 |
| 3 | 数据看板 | `/` | 4个统计卡片 + 6张可视化图表 |
| 4 | 简历管理 | `/resume` | 简历上传、版本列表、删除操作 |
| 5 | 简历审核 | `/resume/review` | 简历解析结果、技能评估、经历展示 |
| 6 | 岗位管理 | `/jobs` | 新增岗位、批量导入、岗位列表 |
| 7 | 岗位审核 | `/jobs/review` | 待审核岗位卡片、通过/驳回操作 |
| 8 | 岗位匹配 | `/jobs/match` | 搜索匹配、匹配分进度条、技能对比 |
| 9 | 多岗对比 | `/jobs/compare` | 基本信息对比表、薪资/匹配度/雷达图 |
| 10 | 模拟面试 | `/interview` | 对话式聊天界面、面试评分 |
| 11 | 面试记录 | `/interview/history` | 面试趋势图、历史列表、报告弹窗 |

## 数据可视化图表（共6张）

| 序号 | 图表类型 | 位置 | 说明 |
|------|---------|------|------|
| 1 | 横向柱状图 | 数据看板 | 简历技能分布 |
| 2 | 纵向柱状图 | 数据看板 | 目标岗位技能要求分布 |
| 3 | 雷达图 | 数据看板 | 个人能力差距（双线对比） |
| 4 | 彩色柱状图 | 数据看板 | 多岗位匹配分数 |
| 5 | 折线图 | 数据看板+面试记录 | 历次面试得分变化 |
| 6 | 饼图 | 数据看板 | 岗位城市分布 |
| 7 | 分组柱状图 | 多岗对比 | 薪资范围对比 |
| 8 | 雷达图 | 多岗对比 | 多岗位技能要求对比 |

## 快速启动

### 环境要求

- Node.js >= 16
- npm >= 7

### 安装依赖

```bash
cd frontend
npm install
```

### 开发模式启动

```bash
# 方式一：仅启动前端（使用内置 Mock 数据）
npm run dev

# 方式二：先启动后端再启动前端（完整体验）
# 终端1 - 启动后端
cd ../backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 终端2 - 启动前端
cd ../frontend
npm run dev
```

启动后访问：**http://localhost:5173**

### 演示账号

- 用户名：`demo`
- 密码：`demo123`

### 生产构建

```bash
npm run build
```

构建产物在 `dist/` 目录，可直接部署到任何静态文件服务器。

## Mock 数据说明

当后端服务不可用时，前端会自动降级使用内置 Mock 数据：

- 登录/注册：使用 `demo / demo123` 账号
- 数据看板：展示模拟的统计数据
- 岗位匹配：返回5个模拟匹配结果
- 模拟面试：使用预设的AI面试官回复

## 测试说明

### 运行测试清单

参考 `tests/manual-test-checklist.js` 执行手动测试，覆盖：

- **正常流程测试**（11个页面 × 1-4个测试点）
- **失败场景测试**（错误登录、空表单、密码不一致、404页面）
- **异常场景测试**（Agent异常、服务器错误、未登录拦截、后端不可用）

### 验证命令

```bash
# 构建验证
npm run build

# 预览构建产物
npm run preview
```

## 项目运行截图指南

建议截取以下页面截图用于课程报告：

1. 登录页面（含演示账号提示）
2. 数据看板概览（含所有图表）
3. 简历上传与管理
4. 简历审核结果详情
5. 岗位管理列表
6. 岗位审核卡片
7. 岗位匹配结果
8. 多岗位对比（含雷达图）
9. 模拟面试对话界面
10. 面试报告弹窗
11. 异常提示页面（404/Agent异常）
