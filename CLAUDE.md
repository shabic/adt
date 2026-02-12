# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目概述

ADT (Android Debug Tools) 是一个 Python CLI 工具，用于 Android 调试和逆向工程。基于 Click 构建 CLI，使用 Rich 美化终端输出，依赖 `adb`（需在 PATH 中）。

## 常用命令

```bash
# 开发安装
pip install -e ".[dev]"

# 运行工具
adt --help

# 测试
pytest

# 格式化与检查
black src/
flake8 src/
```

## 架构

分层设计：CLI → Commands → Core → ADB → Device

- **`src/adt/cli.py`** — Click 入口（`adt.cli:main`），注册所有命令组和顶层命令。
- **`src/adt/core/adb.py`** — `ADB` 类，封装所有 adb 子进程调用。所有设备交互都经过此类。处理设备选择（`-s`）、root 提权（`su -c`）和 shell 转义。
- **`src/adt/core/device.py`** — `DeviceManager`，多设备选择，Rich 交互式表格展示。管道模式下自动选择第一个设备。
- **`src/adt/core/package.py`** — `PackageResolver`，通过 `dumpsys` 检测前台应用，解析包名。
- **`src/adt/core/utils.py`** — 公共校验/转义工具：`escape_shell_arg()`、`validate_package_name()`、`validate_pid()`、`is_piped()`。
- **`src/adt/commands/`** — 按功能域组织的命令实现：`app.py`（应用管理）、`data.py`（备份/恢复/grep，需 root）、`process.py`（进程检查）、`memory.py`（内存 dump）、`input.py`（文本输入）、`utils.py`（ip/getprop/su）。

## 关键约定

- 所有命令支持 `-d DEVICE_ID` 选择设备、可选的 `[PACKAGE]` 位置参数指定包名。省略包名时自动检测前台应用。
- 传给 `adb shell` 的参数必须通过 `core/utils.py` 中的 `escape_shell_arg()` 转义，防止注入。
- 用户输入（包名、PID）必须使用 `core/utils.py` 中的校验函数验证。
- Root 命令使用 `ADB.shell(command, root=True)`，内部以 `su -c` 包装。
- 用户文档（CONTRIBUTING.md、CHANGELOG.md）使用中文，代码和 docstring 使用英文。
- 需兼容 Python 3.8+。依赖：`click>=8.1.0`、`rich>=13.0.0`。
