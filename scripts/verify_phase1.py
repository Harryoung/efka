#!/usr/bin/env python3
"""
Phase 1 验证脚本
检查所有必要的文件和目录是否正确创建
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 必需的目录列表
REQUIRED_DIRS = [
    "backend",
    "backend/agents",
    "backend/services",
    "backend/api",
    "backend/config",
    "backend/utils",
    "backend/logs",
    "frontend",
    "frontend/src",
    "frontend/src/components",
    "frontend/src/hooks",
    "frontend/src/services",
    "frontend/public",
    "knowledge_base",
    "docker",
    "docs",
    "scripts",
    "temp"
]

# 必需的文件列表
REQUIRED_FILES = {
    # 后端文件
    "backend/__init__.py": "Backend package init",
    "backend/main.py": "FastAPI main application",
    "backend/requirements.txt": "Python dependencies",
    "backend/config/__init__.py": "Config package init",
    "backend/config/settings.py": "Settings configuration",
    "backend/agents/__init__.py": "Agents package init",
    "backend/services/__init__.py": "Services package init",
    "backend/api/__init__.py": "API package init",
    "backend/utils/__init__.py": "Utils package init",

    # 前端文件
    "frontend/package.json": "Node.js package config",
    "frontend/vite.config.js": "Vite configuration",
    "frontend/index.html": "HTML entry point",
    "frontend/src/main.jsx": "React main entry",
    "frontend/src/App.jsx": "React App component",
    "frontend/src/App.css": "App styles",

    # 知识库文件
    "knowledge_base/README.md": "Knowledge base structure",
    "knowledge_base/FAQ.md": "FAQ list",

    # 配置文件
    ".env.example": "Environment variables template",
    ".gitignore": "Git ignore rules",
    "README.md": "Project README",

    # 脚本
    "scripts/deploy.sh": "Deployment script"
}

# 文件内容关键词检查
CONTENT_CHECKS = {
    "backend/config/settings.py": ["CLAUDE_API_KEY", "KB_ROOT_PATH", "Settings"],
    "backend/main.py": ["FastAPI", "health_check", "app"],
    "backend/requirements.txt": ["fastapi", "uvicorn", "pydantic"],
    "frontend/package.json": ["react", "vite", "marked"],
    "frontend/vite.config.js": ["defineConfig", "proxy"],
    ".env.example": ["CLAUDE_API_KEY", "KB_ROOT_PATH"],
    "knowledge_base/README.md": ["知识库结构总览"],
    "knowledge_base/FAQ.md": ["常见问题FAQ"]
}


def check_directories():
    """检查所有必需的目录"""
    print("=" * 60)
    print("检查目录结构...")
    print("=" * 60)

    missing_dirs = []
    for dir_path in REQUIRED_DIRS:
        full_path = PROJECT_ROOT / dir_path
        if full_path.exists() and full_path.is_dir():
            print(f"✓ {dir_path}")
        else:
            print(f"✗ {dir_path} [缺失]")
            missing_dirs.append(dir_path)

    return missing_dirs


def check_files():
    """检查所有必需的文件"""
    print("\n" + "=" * 60)
    print("检查必需文件...")
    print("=" * 60)

    missing_files = []
    for file_path, description in REQUIRED_FILES.items():
        full_path = PROJECT_ROOT / file_path
        if full_path.exists() and full_path.is_file():
            print(f"✓ {file_path:<40} ({description})")
        else:
            print(f"✗ {file_path:<40} [缺失] ({description})")
            missing_files.append(file_path)

    return missing_files


def check_file_contents():
    """检查文件内容关键词"""
    print("\n" + "=" * 60)
    print("检查文件内容...")
    print("=" * 60)

    content_errors = []
    for file_path, keywords in CONTENT_CHECKS.items():
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            continue

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            missing_keywords = []
            for keyword in keywords:
                if keyword not in content:
                    missing_keywords.append(keyword)

            if missing_keywords:
                print(f"⚠ {file_path}: 缺少关键词 {missing_keywords}")
                content_errors.append((file_path, missing_keywords))
            else:
                print(f"✓ {file_path}: 内容检查通过")
        except Exception as e:
            print(f"✗ {file_path}: 读取失败 - {e}")
            content_errors.append((file_path, str(e)))

    return content_errors


def check_file_permissions():
    """检查脚本文件的执行权限"""
    print("\n" + "=" * 60)
    print("检查文件权限...")
    print("=" * 60)

    executable_files = ["scripts/deploy.sh"]
    permission_errors = []

    for file_path in executable_files:
        full_path = PROJECT_ROOT / file_path
        if full_path.exists():
            if os.access(full_path, os.X_OK):
                print(f"✓ {file_path}: 可执行")
            else:
                print(f"⚠ {file_path}: 不可执行（已设置但可能需要刷新）")
                permission_errors.append(file_path)
        else:
            print(f"✗ {file_path}: 文件不存在")

    return permission_errors


def print_summary(missing_dirs, missing_files, content_errors, permission_errors):
    """打印总结报告"""
    print("\n" + "=" * 60)
    print("验证总结")
    print("=" * 60)

    total_errors = len(missing_dirs) + len(missing_files) + len(content_errors)

    if total_errors == 0:
        print("\n✅ Phase 1 验证通过！")
        print("\n所有目录和文件已正确创建:")
        print(f"  • {len(REQUIRED_DIRS)} 个目录")
        print(f"  • {len(REQUIRED_FILES)} 个文件")
        print(f"  • 所有内容检查通过")

        if permission_errors:
            print(f"\n⚠️  注意: {len(permission_errors)} 个文件的执行权限可能需要确认")

        print("\n下一步:")
        print("  1. 复制 .env.example 为 .env 并配置 Claude API Key")
        print("  2. 进入 backend 目录创建虚拟环境")
        print("  3. 进入 frontend 目录运行 npm install")
        print("  4. 开始 Phase 2: Agent定义与基础架构")

        return 0
    else:
        print("\n❌ Phase 1 验证失败！")

        if missing_dirs:
            print(f"\n缺失目录 ({len(missing_dirs)}):")
            for dir_path in missing_dirs:
                print(f"  • {dir_path}")

        if missing_files:
            print(f"\n缺失文件 ({len(missing_files)}):")
            for file_path in missing_files:
                print(f"  • {file_path}")

        if content_errors:
            print(f"\n内容错误 ({len(content_errors)}):")
            for file_path, error in content_errors:
                print(f"  • {file_path}: {error}")

        return 1


def main():
    """主函数"""
    print("智能资料库管理员 - Phase 1 验证")
    print(f"项目根目录: {PROJECT_ROOT}")
    print()

    # 执行所有检查
    missing_dirs = check_directories()
    missing_files = check_files()
    content_errors = check_file_contents()
    permission_errors = check_file_permissions()

    # 打印总结
    exit_code = print_summary(missing_dirs, missing_files, content_errors, permission_errors)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
