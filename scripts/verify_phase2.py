#!/usr/bin/env python3
"""
Phase 2 验证脚本
检查 Agent 定义和核心服务的实现是否完整
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# Phase 2 必需的文件列表
REQUIRED_FILES = {
    # Agent 定义文件
    "backend/agents/coordinator.py": "Coordinator Agent definition",
    "backend/agents/document_manager.py": "Document Manager Agent definition",
    "backend/agents/knowledge_qa.py": "Knowledge QA Agent definition",

    # 服务文件
    "backend/services/kb_service.py": "Knowledge Base Service",
    "backend/services/session_manager.py": "Session Manager",
}

# 文件内容关键词检查
CONTENT_CHECKS = {
    "backend/agents/coordinator.py": [
        "COORDINATOR_PROMPT",
        "CoordinatorAgentConfig",
        "get_coordinator_definition",
        "意图识别",
        "Task"
    ],
    "backend/agents/document_manager.py": [
        "DOCUMENT_MANAGER_PROMPT",
        "DocumentManagerAgentConfig",
        "get_document_manager_definition",
        "格式转换",
        "pandoc"
    ],
    "backend/agents/knowledge_qa.py": [
        "KNOWLEDGE_QA_PROMPT",
        "KnowledgeQAAgentConfig",
        "get_knowledge_qa_definition",
        "7阶段",
        "FAQ"
    ],
    "backend/services/kb_service.py": [
        "KnowledgeBaseService",
        "get_kb_service",
        "initialize",
        "query",
        "agents_config"
    ],
    "backend/services/session_manager.py": [
        "SessionManager",
        "Session",
        "get_session_manager",
        "create_session",
        "cleanup_expired_sessions"
    ]
}

# Agent Prompt 长度检查（确保 prompt 足够详细）
MIN_PROMPT_LENGTH = {
    "backend/agents/coordinator.py": 2000,   # Coordinator prompt 应该 > 2000 字符
    "backend/agents/document_manager.py": 3000,  # Document Manager 更复杂
    "backend/agents/knowledge_qa.py": 4000   # Knowledge QA 最复杂
}


def check_files():
    """检查所有必需的文件"""
    print("=" * 60)
    print("检查 Phase 2 文件...")
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


def check_prompt_length():
    """检查 Agent Prompt 的长度"""
    print("\n" + "=" * 60)
    print("检查 Agent Prompt 长度...")
    print("=" * 60)

    prompt_errors = []
    for file_path, min_length in MIN_PROMPT_LENGTH.items():
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            continue

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 查找 PROMPT 变量（支持普通字符串和原始字符串）
            if "_PROMPT = \"\"\"" in content or "_PROMPT = r\"\"\"" in content:
                # 找到 PROMPT 定义的开始
                if "_PROMPT = r\"\"\"" in content:
                    prompt_start = content.find("_PROMPT = r\"\"\"") + len("_PROMPT = r\"\"\"")
                else:
                    prompt_start = content.find("_PROMPT = \"\"\"") + len("_PROMPT = \"\"\"")

                prompt_end = content.find("\"\"\"", prompt_start)
                if prompt_end > prompt_start:
                    prompt_length = prompt_end - prompt_start
                    if prompt_length >= min_length:
                        print(f"✓ {file_path}: Prompt 长度 {prompt_length} 字符 (>= {min_length})")
                    else:
                        print(f"⚠ {file_path}: Prompt 长度 {prompt_length} 字符 (< {min_length})")
                        prompt_errors.append((file_path, prompt_length, min_length))
                else:
                    print(f"✗ {file_path}: 无法找到 Prompt 结束标记")
                    prompt_errors.append((file_path, 0, min_length))
            else:
                print(f"✗ {file_path}: 无法找到 Prompt 定义")
                prompt_errors.append((file_path, 0, min_length))
        except Exception as e:
            print(f"✗ {file_path}: 检查失败 - {e}")
            prompt_errors.append((file_path, 0, min_length))

    return prompt_errors


def check_agent_definitions():
    """检查 Agent 定义函数是否可调用"""
    print("\n" + "=" * 60)
    print("检查 Agent 定义函数...")
    print("=" * 60)

    agent_errors = []

    # 将项目根目录添加到 Python 路径
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    agents_to_test = [
        ("coordinator", "get_coordinator_definition"),
        ("document_manager", "get_document_manager_definition"),
        ("knowledge_qa", "get_knowledge_qa_definition")
    ]

    for module_name, function_name in agents_to_test:
        try:
            # 动态导入
            module = __import__(f"backend.agents.{module_name}", fromlist=[function_name])
            func = getattr(module, function_name)

            # 调用函数获取定义
            definition = func()

            # 验证定义格式
            if not isinstance(definition, dict):
                print(f"✗ {module_name}: 定义不是字典类型")
                agent_errors.append((module_name, "返回类型错误"))
                continue

            required_keys = ["description", "prompt", "tools", "model"]
            missing_keys = [k for k in required_keys if k not in definition]

            if missing_keys:
                print(f"⚠ {module_name}: 定义缺少字段 {missing_keys}")
                agent_errors.append((module_name, f"缺少字段: {missing_keys}"))
            else:
                print(f"✓ {module_name}: Agent 定义格式正确")

        except Exception as e:
            print(f"✗ {module_name}: 导入或调用失败 - {e}")
            agent_errors.append((module_name, str(e)))

    return agent_errors


def check_service_classes():
    """检查服务类是否可以实例化"""
    print("\n" + "=" * 60)
    print("检查服务类...")
    print("=" * 60)

    service_errors = []

    # 将项目根目录添加到 Python 路径
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    services_to_test = [
        ("backend.services.kb_service", "KnowledgeBaseService", "get_kb_service"),
        ("backend.services.session_manager", "SessionManager", "get_session_manager")
    ]

    for module_name, class_name, function_name in services_to_test:
        try:
            # 动态导入
            module = __import__(module_name, fromlist=[class_name, function_name])

            # 测试类
            cls = getattr(module, class_name)
            print(f"✓ {class_name}: 类定义正确")

            # 测试获取函数
            func = getattr(module, function_name)
            instance = func()
            print(f"✓ {function_name}: 单例函数正常")

        except Exception as e:
            print(f"✗ {module_name}: 检查失败 - {e}")
            service_errors.append((module_name, str(e)))

    return service_errors


def print_summary(missing_files, content_errors, prompt_errors, agent_errors, service_errors):
    """打印总结报告"""
    print("\n" + "=" * 60)
    print("Phase 2 验证总结")
    print("=" * 60)

    total_errors = (
        len(missing_files) +
        len(content_errors) +
        len(prompt_errors) +
        len(agent_errors) +
        len(service_errors)
    )

    if total_errors == 0:
        print("\n✅ Phase 2 验证通过！")
        print("\n所有 Agent 和服务已正确实现:")
        print("  ✓ Coordinator Agent - 意图识别与任务分发")
        print("  ✓ Document Manager Agent - 文档入库与管理")
        print("  ✓ Knowledge QA Agent - 智能问答（7阶段检索）")
        print("  ✓ KnowledgeBaseService - 知识库核心服务")
        print("  ✓ SessionManager - 会话管理")

        print("\n下一步:")
        print("  1. 安装依赖: cd backend && pip install -r requirements.txt")
        print("  2. 配置 .env: cp .env.example .env && 填入 CLAUDE_API_KEY")
        print("  3. 开始 Phase 3: WebSocket 通信实现")

        return 0
    else:
        print("\n❌ Phase 2 验证失败！")

        if missing_files:
            print(f"\n缺失文件 ({len(missing_files)}):")
            for file_path in missing_files:
                print(f"  • {file_path}")

        if content_errors:
            print(f"\n内容错误 ({len(content_errors)}):")
            for file_path, error in content_errors:
                print(f"  • {file_path}: {error}")

        if prompt_errors:
            print(f"\nPrompt 长度不足 ({len(prompt_errors)}):")
            for file_path, actual, expected in prompt_errors:
                print(f"  • {file_path}: {actual} 字符 (期望 >= {expected})")

        if agent_errors:
            print(f"\nAgent 定义错误 ({len(agent_errors)}):")
            for agent_name, error in agent_errors:
                print(f"  • {agent_name}: {error}")

        if service_errors:
            print(f"\n服务类错误 ({len(service_errors)}):")
            for service_name, error in service_errors:
                print(f"  • {service_name}: {error}")

        return 1


def main():
    """主函数"""
    print("智能资料库管理员 - Phase 2 验证")
    print(f"项目根目录: {PROJECT_ROOT}")
    print()

    # 设置临时环境变量（仅用于验证）
    os.environ["CLAUDE_API_KEY"] = "test_key_for_verification"
    os.environ["KB_ROOT_PATH"] = str(PROJECT_ROOT / "knowledge_base")

    # 执行所有检查
    missing_files = check_files()
    content_errors = check_file_contents()
    prompt_errors = check_prompt_length()
    agent_errors = check_agent_definitions()
    service_errors = check_service_classes()

    # 打印总结
    exit_code = print_summary(
        missing_files,
        content_errors,
        prompt_errors,
        agent_errors,
        service_errors
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
