# AGENTS.md

MediaConveyor：一个监听目录并调用 FFmpeg 处理音视频文件的 Python 工具（单进程、`src/` 扁平包结构、入口 `main.py`）。

## 代码规范性要求

- 如果现有代码结构无法规范、优雅地实现维护者的需求：

  - 大胆增/删/改写模块，以保持低耦合、高内聚，避免出现补丁式代码。
  - 允许引入新库，不要为了“不增加依赖”而频繁自己造轮子。
  
- 如果：

  - 不确定某个功能应该使用何种方案来实现
  - 应该如何处理某种维护者未提及的情况
  - 维护者的需求描述或功能设计中有无法自洽的内容，或 Agent 认为有更好的方案
  - 有其他任何不确定的问题

  请向维护者询问。可在开发过程中多次询问，直至所有细节清晰。

## 常用命令

```bash
pip install -r requirements.txt   # 只有 toml + humanfriendly；pytest 不在其中
pip install pytest                # CI 是单独安装 pytest 的
python -m pytest                  # 全部测试（pytest.ini 已设 pythonpath=. 和 testpaths=tests）
python -m pytest tests/test_filter.py -v   # 单个测试文件
python main.py                    # 必须在仓库根目录运行
```

- 测试完全离线运行（约 2 秒）：ffmpeg/ffprobe、`subprocess`、文件移动均被 mock。只有真正运行程序才需要安装 FFmpeg。
- `python main.py` 需要 `config/config.toml`（从 `config/config.example.toml` 复制）以及 PATH 中的 `ffmpeg`。

## 路径基于当前工作目录，而非仓库根目录

`Config` 默认读 `config/config.toml`，`DBManager` 默认用 `data/media-conveyor.db`，日志写到 `logs/` —— 全部相对当前工作目录解析。务必在仓库根目录运行。`config.toml`、`data/`、`logs/` 是被 gitignore 的运行时产物（不要提交）。

## 架构要点

- 流程：`main.py` → `Scanner`（`src/scanner.py`）→ 过滤流水线（`src/filter.py`）→ `Processor`（`src/processor.py`，通过 `shell=True` 执行 ffmpeg）→ 状态写入 SQLite（`src/db_manager.py`，表 `file_state`：`success_time`、`failure_count`、`ffmpeg_failure_count`）。防止重复处理靠的就是数据库记录。
- 过滤按流水线顺序执行：`include_patterns` → `exclude_patterns` → `passthrough_patterns`（用 fnmatch 匹配相对 `source_dir` 的路径）。只有配置了媒体属性过滤条件（时长/码率/帧率/短边/编码）时才会调用 ffprobe。
- `ffmpeg_cmd` 模板通过 Python `.format()` 填充 `{input}` / `{output}` —— 命令中出现字面量 `{` 会直接抛异常；命令中的路径要加引号。
- `main.py` 的单实例锁使用 `fcntl`（仅 POSIX），在 Windows 上刻意降级为警告。不要试图为 Windows "修复" 它。
- 配置校验错误（如缺少 `[global]`、任务必填键 `source_dir`/`dest_dir`/`ffmpeg_cmd`）由 `src/config.py` / `src/task_config.py` 在启动时抛出。

## 平台与 CI

- CI 有两个工作流：
  - `.github/workflows/tests.yml`：在 ubuntu + windows、Python 3.11–3.14 上运行 `pytest`。
  - `.github/workflows/docker-publish.yml`：发布时构建并推送 Docker 镜像（详见 RELEASE-GUIDE.md）。
- 没有配置任何 linter、formatter 或 typechecker —— `pytest` 是唯一的自动化检查。
- 代码必须保持跨平台；Docker 运行环境是基于 Debian 的，带 GPU/VAAPI 驱动。

## 提交与发布（权威文档：RELEASE-GUIDE.md）

- 仅当维护者主动要求时执行对应流程，不得自行提交、推送或发布：
  - 要求提交变更 → 执行 RELEASE-GUIDE.md 的提交流程（前置：仓库存在未提交的变更）。
  - 要求发布版本 → 执行 RELEASE-GUIDE.md 的发布流程（前置：`VERSION` 文件存在未提交的变更）。

## 约定

- 默认分支为 `dev`；CI 在 `master` 和 `dev` 上都会运行。
- 提交信息使用 Conventional Commits 前缀（`feat:`、`fix:`、`refactor(scope):`、`chore!:` 表破坏性变更），描述用中文，如 `feat(tasks): 引入基于 fnmatch 的文件过滤流水线`。
- 面向用户的字符串 —— 日志、错误信息、README —— 用中文；测试和 CI 用英文。遵循这一分工。
- README.md 是 `config.toml` 的中文配置向导；新增配置项时，需同时更新 README.md 和 `config/config.example.toml`。
