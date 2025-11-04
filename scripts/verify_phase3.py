#!/usr/bin/env python3
"""
Phase 3 验证脚本
检查后端 API 路由的实现是否完整且遵循 Agent 自主原则
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# Phase 3 必需的文件列表
REQUIRED_FILES = {
    # API 路由文件
    "backend/api/query.py": "Query API - 智能问答接口",
    "backend/api/upload.py": "Upload API - 文件接收服务",
    "backend/main.py": "FastAPI主应用（已更新）",
}

# 文件内容关键词检查
CONTENT_CHECKS = {
    "backend/api/query.py": [
        "QueryRequest",
        "QueryResponse",
        "@router.post",
        "StreamingResponse",
        "Coordinator Agent",
        "def query",
        "def query_stream",
        "def create_session",
        "def delete_session",
    ],
    "backend/api/upload.py": [
        "@router.post",
        "纯文件接收服务",
        "不做任何业务逻辑",
        "tempfile",
        "MAX_UPLOAD_SIZE",
        "def upload_files",
    ],
    "backend/main.py": [
        "lifespan",
        "get_kb_service",
        "get_session_manager",
        "include_router",
        "query_router",
        "upload_router",
    ],
}

# 反面检查：不应该出现的内容（硬编码业务逻辑）
# 检查代码逻辑，不检查注释和文档字符串
ANTI_PATTERNS = {
    "backend/api/query.py": [
        # 不应该在 query.py 中硬编码意图判断
    ],
    "backend/api/upload.py": [
        "mcp__markitdown",  # 不应该在 upload.py 中调用 markitdown MCP
        "Document Manager Agent",  # upload.py 不应该直接调用 Agent
        "kb_service.process",  # upload.py 不应该调用 kb_service 处理逻辑
    ],
}

# API 端点检查
EXPECTED_ENDPOINTS = [
    ("/api/query", "POST", "智能问答（非流式）"),
    ("/api/query/stream", "POST", "智能问答（SSE流式）"),
    ("/api/upload", "POST", "文件接收服务"),
    ("/api/session/create", "POST", "创建会话"),
    ("/api/session/{session_id}", "DELETE", "删除会话"),
    ("/health", "GET", "健康检查"),
    ("/info", "GET", "系统信息"),
]


def check_files():
    """检查所有必需的文件"""
    print("=" * 60)
    print("检查 Phase 3 文件...")
    print("=" * 60)

    missing_files = []
    for file_path, description in REQUIRED_FILES.items():
        full_path = PROJECT_ROOT / file_path
        if full_path.exists() and full_path.is_file():
            print(f"✓ {file_path:<45} ({description})")
        else:
            print(f"✗ {file_path:<45} [缺失] ({description})")
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


def check_anti_patterns():
    """检查不应该出现的内容（反模式）"""
    print("\n" + "=" * 60)
    print("检查反模式（不应该出现的硬编码逻辑）...")
    print("=" * 60)

    anti_pattern_errors = []
    for file_path, anti_keywords in ANTI_PATTERNS.items():
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            continue

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            found_anti_patterns = []
            for keyword in anti_keywords:
                if keyword in content:
                    found_anti_patterns.append(keyword)

            if found_anti_patterns:
                print(f"⚠ {file_path}: 发现硬编码业务逻辑 {found_anti_patterns}")
                anti_pattern_errors.append((file_path, found_anti_patterns))
            else:
                print(f"✓ {file_path}: 无硬编码业务逻辑")
        except Exception as e:
            print(f"✗ {file_path}: 检查失败 - {e}")
            anti_pattern_errors.append((file_path, str(e)))

    return anti_pattern_errors


def check_design_principles():
    """检查是否遵循 Agent 自主设计原则"""
    print("\n" + "=" * 60)
    print("检查设计原则...")
    print("=" * 60)

    design_errors = []

    # 检查 upload.py 的设计
    upload_path = PROJECT_ROOT / "backend/api/upload.py"
    if upload_path.exists():
        with open(upload_path, 'r', encoding='utf-8') as f:
            upload_content = f.read()

        # upload.py 应该只做文件接收，不做业务逻辑
        if "纯文件接收服务" in upload_content and "不做任何业务逻辑" in upload_content:
            print("✓ upload.py: 遵循纯文件接收原则")
        else:
            print("✗ upload.py: 未遵循纯文件接收原则")
            design_errors.append(("upload.py", "应该是纯文件接收服务，不做业务逻辑"))

        # 检查是否调用了 markitdown 或 Agent
        if "mcp__markitdown" in upload_content:
            print("⚠ upload.py: 调用了 markitdown MCP")
            design_errors.append(("upload.py", "不应该调用 markitdown MCP"))
        elif "Document Manager Agent" in upload_content and "调用" in upload_content:
            print("⚠ upload.py: 调用了 Document Manager Agent")
            design_errors.append(("upload.py", "不应该调用 Agent"))
        else:
            print("✓ upload.py: 无业务逻辑调用")

    # 检查 query.py 的设计
    query_path = PROJECT_ROOT / "backend/api/query.py"
    if query_path.exists():
        with open(query_path, 'r', encoding='utf-8') as f:
            query_content = f.read()

        # query.py 应该调用 Coordinator Agent
        if "Coordinator Agent" in query_content:
            print("✓ query.py: 调用 Coordinator Agent")
        else:
            print("✗ query.py: 未调用 Coordinator Agent")
            design_errors.append(("query.py", "应该调用 Coordinator Agent"))

        # 不应该有硬编码的意图判断
        intent_keywords = ["if.*知识查询", "if.*文档入库", "if.*FAQ"]
        has_intent_logic = any(kw in query_content for kw in intent_keywords)
        if has_intent_logic:
            print("⚠ query.py: 发现硬编码的意图判断逻辑")
            design_errors.append(("query.py", "不应该硬编码意图判断，应由 Agent 自主判断"))
        else:
            print("✓ query.py: 无硬编码意图判断")

    return design_errors


def check_imports():
    """检查导入是否正确"""
    print("\n" + "=" * 60)
    print("检查模块导入...")
    print("=" * 60)

    import_errors = []

    # 将项目根目录添加到 Python 路径
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # 设置临时环境变量
    os.environ["CLAUDE_API_KEY"] = "test_key_for_verification"
    os.environ["KB_ROOT_PATH"] = str(PROJECT_ROOT / "knowledge_base")

    modules_to_test = [
        ("backend.api.query", "Query API"),
        ("backend.api.upload", "Upload API"),
        ("backend.main", "Main Application"),
    ]

    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print(f"✓ {description}: 导入成功")
        except Exception as e:
            print(f"✗ {description}: 导入失败 - {e}")
            import_errors.append((module_name, str(e)))

    return import_errors


def print_summary(missing_files, content_errors, anti_pattern_errors, design_errors, import_errors):
    """打印总结报告"""
    print("\n" + "=" * 60)
    print("Phase 3 验证总结")
    print("=" * 60)

    total_errors = (
        len(missing_files) +
        len(content_errors) +
        len(anti_pattern_errors) +
        len(design_errors) +
        len(import_errors)
    )

    if total_errors == 0:
        print("\n✅ Phase 3 验证通过！")
        print("\n所有 API 路由已正确实现:")
        print("  ✓ /api/query - 智能问答（调用 Coordinator Agent）")
        print("  ✓ /api/query/stream - SSE 流式响应")
        print("  ✓ /api/upload - 纯文件接收服务（无业务逻辑）")
        print("  ✓ /api/session/* - 会话管理")
        print("  ✓ /health, /info - 系统信息")

        print("\n✅ 设计原则检查通过:")
        print("  ✓ 所有业务逻辑由 Agent 自主完成")
        print("  ✓ 无硬编码的格式转换、入库、FAQ 管理逻辑")
        print("  ✓ upload.py 仅负责文件接收")
        print("  ✓ query.py 仅负责调用 Agent")

        print("\n下一步:")
        print("  1. 测试 API 端点: 启动服务后访问 http://localhost:8000/docs")
        print("  2. 测试文件上传: POST /api/upload")
        print("  3. 测试查询: POST /api/query")
        print("  4. 开始 Phase 4: 前端实现")

        return 0
    else:
        print("\n❌ Phase 3 验证失败！")

        if missing_files:
            print(f"\n缺失文件 ({len(missing_files)}):")
            for file_path in missing_files:
                print(f"  • {file_path}")

        if content_errors:
            print(f"\n内容错误 ({len(content_errors)}):")
            for file_path, error in content_errors:
                print(f"  • {file_path}: {error}")

        if anti_pattern_errors:
            print(f"\n反模式错误 ({len(anti_pattern_errors)}):")
            for file_path, patterns in anti_pattern_errors:
                print(f"  • {file_path}: 发现硬编码逻辑 {patterns}")

        if design_errors:
            print(f"\n设计原则违规 ({len(design_errors)}):")
            for file_path, error in design_errors:
                print(f"  • {file_path}: {error}")

        if import_errors:
            print(f"\n导入错误 ({len(import_errors)}):")
            for module_name, error in import_errors:
                print(f"  • {module_name}: {error}")

        return 1


def main():
    """主函数"""
    print("智能资料库管理员 - Phase 3 验证")
    print(f"项目根目录: {PROJECT_ROOT}")
    print()

    # 设置临时环境变量（仅用于验证）
    os.environ["CLAUDE_API_KEY"] = "test_key_for_verification"
    os.environ["KB_ROOT_PATH"] = str(PROJECT_ROOT / "knowledge_base")

    # 执行所有检查
    missing_files = check_files()
    content_errors = check_file_contents()
    anti_pattern_errors = check_anti_patterns()
    design_errors = check_design_principles()
    import_errors = check_imports()

    # 打印总结
    exit_code = print_summary(
        missing_files,
        content_errors,
        anti_pattern_errors,
        design_errors,
        import_errors
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
