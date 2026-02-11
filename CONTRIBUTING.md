# Contributing to ADT

感谢你对 ADT 的关注！欢迎任何形式的贡献。

## 如何贡献

### 报告 Bug

请通过 GitHub Issues 提交，包含以下信息：

- 操作系统和 Python 版本
- ADB 版本 (`adb version`)
- 设备信息（如适用）
- 复现步骤
- 期望行为 vs 实际行为

### 提交功能建议

通过 GitHub Issues 提交，描述你的使用场景和期望的功能。

### 提交代码

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "Add your feature"`
4. 推送分支：`git push origin feature/your-feature`
5. 创建 Pull Request

### 开发环境搭建

```bash
git clone https://github.com/yourusername/adt.git
cd adt
pip install -e ".[dev]"
```

### 代码规范

- 遵循 PEP 8
- 使用 type hints
- 为公共函数添加 docstring
- Shell 参数必须转义（使用 `core/utils.py` 中的工具函数）
- 用户输入必须验证

## License

贡献的代码将以 MIT 协议发布。
