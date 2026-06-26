# Changelog

All notable changes to the hermes-xiaoxi project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.1] — 2026-06-26

### Added
- **用户认证系统**：JWT 登录/注册，bcrypt 密码加密，token 自动持久化
- **三级权限体系**：`admin` / `operator` / `observer` 角色，注册自动降级防越权
- **用户管理页面**：管理员在 APP 设置页可查看所有用户、修改角色
- **注册同步创建联系人**：新用户注册后自动生成 `type=user` 的智能体条目，即时出现在联系人列表
- **聊天列表排序与置顶**：调度员优先 → 手动置顶 → 在线状态 → 离线，支持长按设置置顶
- **联系人搜索**：按名称/ID 实时过滤
- **APP 内注册智能体**：联系人页底部"注册新智能体"表单，支持声明能力模块
- **智能体能力编辑**：设置页可增删能力模块（逗号分隔）
- **暗色模式**：聊天/联系人/设置/详情页全量覆盖，一键切换
- **用户删除**：管理页可删除用户，需输入 `OK` 二次确认

### Changed
- **仓库重构**：`xiaoxi-mesh` → `hermes-xiaoxi`，三模块合一（xiaoqing-app / task-dispatcher / xiaoxi-mesh）
- **Flutter 3.44**：全面兼容最新 SDK，移除弃用 API
- **WebSocket 通信**：连接稳定性优化，断线重连机制
- **dialog 管理**：统一 AlertDialog 样式，关闭后清理资源

### Architecture
- `task-dispatcher/routes/auth.py` — 新增完整 JWT 认证路由
- `xiaoxi-mesh/` — v2 演进：agent_runner、permissions 权限系统、decision_engine 决策引擎、executors 执行器框架
- `xiaoqing-app/lib/screens/login_screen.dart` — 新增登录/注册页面
- `xiaoqing-app/lib/models/user.dart` — 新增用户数据模型
- `xiaoqing-app/lib/screens/settings_screen.dart` — 重写设置页，新增用户管理、暗色模式

**Files changed:** 61 files, +4911/-1659 lines

---

## [0.1.0] — 2026-06-10

### Added
- 项目初始化，三模块骨架
- `xiaoqing-app/` — Flutter 跨平台移动端，微信风格三标签界面
- `task-dispatcher/` — FastAPI 调度器，智能体注册/任务分配/记忆管理/MESH 通信
- `xiaoxi-mesh/` — 多智能体通信协议，支持 WebSocket + SSH 远程执行
- Web 前端 5 页面：聊天、智能体管理、系统配置、记忆管理、调度面板
- 智能体分组展示（调度员/智能体/用户）
- 基础 REST API：智能体 CRUD、聊天会话、记忆存储

### Architecture
- 三模块架构：client/ (Web) + server/ (FastAPI) + app/ (Flutter)
- SQLite 本地持久化存储
- OpenAI 兼容格式 API 端点

---

## Template

```markdown
## [Unreleased]

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 
```

---

## How to Release

1. Update version in `xiaoqing-app/pubspec.yaml`
2. Run `flutter build apk --debug`
3. Update `CHANGELOG.md` with the new version
4. Create a git tag: `git tag v<version>`
5. Push: `git push origin main --tags`
6. Update website at `mesh.xixisz.top`
