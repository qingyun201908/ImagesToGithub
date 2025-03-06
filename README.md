# 自动化图床工具使用文档

## 工具概述

本工具用于自动化管理Markdown文档中的图片资源，主要实现以下功能：

1. 🖼️ 自动检测并处理Markdown文件中的本地图片引用
2. ⬆️ 将图片上传至GitHub仓库作为图床
3. 💾 本地同步保存图片备份
4. 🔍 基于SHA-256哈希值的修改检测机制
5. 📊 支持批量处理多篇Markdown文档

## 环境要求

- Python 3.8+
- 所需库：`PyGithub`, `pathlib`
- GitHub账号及有效访问Token

## 配置文件说明

在用户目录创建`.image_upload_config.json`：

```json
{
    "GITHUB_TOKEN": "你的GitHub个人访问令牌"
}
