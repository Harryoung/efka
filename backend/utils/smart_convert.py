#!/usr/bin/env python3
import os
import sys
import json
import argparse
import shutil
import subprocess
import base64
import requests
import fitz  # PyMuPDF
import pypandoc
import pymupdf4llm
import pathlib

# ================= 配置区域 =================
# PaddleOCR API Token (默认使用你提供的)
DEFAULT_PADDLE_TOKEN = "9bd0989698f6e1c63a4c79ec0dae66c0356cd782"
PADDLE_API_URL = "https://1fx7w5m1a19fg4aa.aistudio-app.com/layout-parsing"

# LibreOffice 路径 (Mac 通常需要指定完整路径，Linux 通常在 PATH 中)
# 如果在 Mac 上找不到 soffice 命令，脚本会尝试使用这个默认路径
MAC_SOFFICE_PATH = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
# ===========================================

def is_scanned_pdf(pdf_path):
    """检测 PDF 是否为扫描版 (检查前3页文本密度)"""
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0: return False

        check_pages = min(3, len(doc))
        text_length = 0
        has_images = False

        for i in range(check_pages):
            page = doc[i]
            text = page.get_text().strip()
            text_length += len(text)
            if len(page.get_images()) > 0:
                has_images = True

        doc.close()

        # 判定逻辑：如果有图片且前几页总字符数极少，视为扫描版
        # 阈值设为 50 字符，防止页码等干扰
        return has_images and text_length < 50
    except Exception as e:
        print(f"[Warning] PDF 检测失败，默认按非扫描版处理: {e}", file=sys.stderr)
        return False

def convert_doc_to_docx(input_path):
    """使用 LibreOffice 将 .doc 转为 .docx"""
    print(f" -> 正在将 .doc 转换为 .docx: {input_path}", file=sys.stderr)

    input_abs_path = os.path.abspath(input_path)
    output_dir = os.path.dirname(input_abs_path)

    # 确定 soffice 命令
    soffice_cmd = "soffice"
    if sys.platform == "darwin" and not shutil.which("soffice"):
        if os.path.exists(MAC_SOFFICE_PATH):
            soffice_cmd = MAC_SOFFICE_PATH
        else:
            raise FileNotFoundError("未找到 LibreOffice (soffice)。请安装 LibreOffice 或将其加入 PATH。")

    cmd = [
        soffice_cmd, '--headless', '--convert-to', 'docx',
        input_abs_path, '--outdir', output_dir
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice 转换失败: {result.stderr.decode()}")

    # 推断输出文件路径
    docx_path = input_abs_path + "x" # simple append logic usually used by LibreOffice if extension exists
    # LibreOffice 行为通常是将 .doc 替换为 .docx
    base_name = os.path.splitext(input_abs_path)[0]
    docx_candidate = base_name + ".docx"

    if os.path.exists(docx_candidate):
        return docx_candidate
    else:
        # Fallback 检查
        return docx_path if os.path.exists(docx_path) else None

def process_pandoc(input_file, output_file):
    """处理 Word (.docx) -> Markdown

    Returns:
        dict: 包含转换结果信息 (images_dir, image_count)
    """
    output_dir = os.path.dirname(os.path.abspath(output_file))
    filename_no_ext = os.path.splitext(os.path.basename(output_file))[0]
    media_dir_name = f"{filename_no_ext}_images"
    media_dir = os.path.join(output_dir, media_dir_name)

    print(f" -> 使用 Pandoc 转换 (保留格式与图片)...", file=sys.stderr)

    pypandoc.convert_file(
        input_file,
        'markdown',
        outputfile=output_file,
        extra_args=[
            f'--extract-media={media_dir}',
            '--wrap=none',
            '--standalone'
        ]
    )

    # 统计图片数量
    image_count = 0
    if os.path.exists(media_dir):
        for root, dirs, files in os.walk(media_dir):
            image_count += len([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'))])

    return {
        "images_dir": media_dir_name if os.path.exists(media_dir) else None,
        "image_count": image_count
    }

def process_pymupdf(input_file, output_file):
    """处理电子版 PDF -> Markdown

    Returns:
        dict: 包含转换结果信息 (images_dir, image_count)
    """
    output_dir = os.path.dirname(os.path.abspath(output_file))
    filename_no_ext = os.path.splitext(os.path.basename(output_file))[0]
    images_folder_name = f"{filename_no_ext}_images"

    print(f" -> 使用 PyMuPDF4LLM 转换 (本地快速模式)...", file=sys.stderr)

    # 转换
    md_text = pymupdf4llm.to_markdown(
        input_file,
        write_images=True,
        image_path=images_folder_name,
        image_format="png"
    )

    # 写入 Markdown
    pathlib.Path(output_file).write_bytes(md_text.encode('utf-8'))

    # 移动图片目录 (PyMuPDF 默认在当前工作目录生成图片文件夹)
    cwd_image_dir = os.path.join(os.getcwd(), images_folder_name)
    target_image_dir = os.path.join(output_dir, images_folder_name)

    if os.getcwd() != output_dir and os.path.exists(cwd_image_dir):
        if os.path.exists(target_image_dir):
            shutil.rmtree(target_image_dir)
        shutil.move(cwd_image_dir, target_image_dir)

    # 统计图片数量
    image_count = 0
    if os.path.exists(target_image_dir):
        for root, dirs, files in os.walk(target_image_dir):
            image_count += len([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg'))])

    return {
        "images_dir": images_folder_name if os.path.exists(target_image_dir) else None,
        "image_count": image_count
    }

def process_paddle_ocr(input_file, output_file, token):
    """处理扫描版 PDF -> Markdown (PaddleOCR API)

    Returns:
        dict: 包含转换结果信息 (images_dir, image_count)
    """
    print(f" -> 使用 PaddleOCR-VL 在线服务转换 (扫描版模式)...", file=sys.stderr)
    print(f" ⚠️  警告: 扫描版PDF处理可能需要几十秒到几分钟，请耐心等待...", file=sys.stderr)

    output_dir = os.path.dirname(os.path.abspath(output_file))
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 统一图片目录命名
    filename_no_ext = os.path.splitext(os.path.basename(output_file))[0]
    images_folder_name = f"{filename_no_ext}_images"
    images_dir = os.path.join(output_dir, images_folder_name)
    os.makedirs(images_dir, exist_ok=True)

    # 1. 读取文件并编码
    with open(input_file, "rb") as file:
        file_bytes = file.read()
        file_data = base64.b64encode(file_bytes).decode("ascii")

    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json"
    }

    # 2. 发送请求
    payload = {
        "file": file_data,
        "fileType": 0, # 0 for PDF
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": True, # 建议开启图表识别
    }

    print("    正在上传并等待 AI 解析 (可能需要几十秒)...", file=sys.stderr)
    response = requests.post(PADDLE_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        raise Exception(f"API 请求失败: Code {response.status_code}, Info: {response.text}")

    result = response.json().get("result", {})
    if not result:
        raise Exception("API 返回结果为空")

    # 3. 处理结果
    # Paddle 可能会把 PDF 分页返回，我们需要合并 Markdown
    full_markdown = []
    image_count = 0

    for i, res in enumerate(result.get("layoutParsingResults", [])):
        md_content = res["markdown"]["text"]

        # 修改markdown中的图片路径引用，从 "images/xxx.jpg" 改为 "{filename}_images/xxx.jpg"
        # PaddleOCR返回的markdown里图片路径通常是 "images/xxx.jpg"
        md_content = md_content.replace("images/", f"{images_folder_name}/")

        full_markdown.append(md_content)

        # 处理文中插图
        images_dict = res["markdown"].get("images", {})
        if images_dict:
            print(f"    正在下载第 {i+1} 页的插图 ({len(images_dict)} 张)...", file=sys.stderr)

        for relative_path, img_url in images_dict.items():
            # relative_path 原本是 "images/demo_0.jpg"
            # 我们需要改为 "{filename}_images/demo_0.jpg"
            # 提取文件名
            img_filename = os.path.basename(relative_path)
            new_relative_path = os.path.join(images_folder_name, img_filename)
            full_save_path = os.path.join(output_dir, new_relative_path)

            # 确保子文件夹存在
            os.makedirs(os.path.dirname(full_save_path), exist_ok=True)

            # 下载图片
            try:
                img_bytes = requests.get(img_url).content
                with open(full_save_path, "wb") as img_file:
                    img_file.write(img_bytes)
                image_count += 1
            except Exception as e:
                print(f"    [Warning] 图片下载失败 {new_relative_path}: {e}", file=sys.stderr)

    # 4. 写入合并后的 Markdown
    final_md_text = "\n\n---\n\n".join(full_markdown)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(final_md_text)

    print(f"    处理完成，已合并 {len(full_markdown)} 页内容。", file=sys.stderr)

    return {
        "images_dir": images_folder_name if image_count > 0 else None,
        "image_count": image_count
    }

def main():
    parser = argparse.ArgumentParser(description="智能文档转 Markdown 工具 (支持 docx/doc/pdf/扫描件)")
    parser.add_argument("input", help="输入文件路径")
    parser.add_argument("-o", "--output", help="输出 Markdown 文件路径 (默认同名)")
    parser.add_argument("--token", default=DEFAULT_PADDLE_TOKEN, help="PaddleOCR API Token")
    parser.add_argument("--force-ocr", action="store_true", help="强制使用 OCR 模式处理 PDF")
    parser.add_argument("--json-output", action="store_true", help="输出JSON格式结果（便于程序解析）")

    args = parser.parse_args()

    input_file = args.input
    if not os.path.exists(input_file):
        error_msg = f"❌ 错误: 文件不存在 {input_file}"
        print(error_msg, file=sys.stderr)
        if args.json_output:
            print(json.dumps({"success": False, "error": error_msg}))
        sys.exit(1)

    # 确定输出路径
    if args.output:
        output_file = args.output
    else:
        base = os.path.splitext(input_file)[0]
        output_file = base + ".md"

    # 确保输出目录存在
    output_dir = os.path.dirname(os.path.abspath(output_file))
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    ext = os.path.splitext(input_file)[1].lower()
    temp_docx = None
    conversion_info = {}

    try:
        # === 分流逻辑 ===

        # 1. DOC 处理
        if ext == ".doc":
            temp_docx = convert_doc_to_docx(input_file)
            if not temp_docx:
                error_msg = "❌ .doc 转 .docx 失败"
                print(error_msg, file=sys.stderr)
                if args.json_output:
                    print(json.dumps({"success": False, "error": error_msg}))
                sys.exit(1)
            conversion_info = process_pandoc(temp_docx, output_file)

        # 2. DOCX 处理
        elif ext == ".docx":
            conversion_info = process_pandoc(input_file, output_file)

        # 3. PDF 处理
        elif ext == ".pdf":
            is_scanned = False
            if args.force_ocr:
                print(" -> 用户强制指定 OCR 模式", file=sys.stderr)
                is_scanned = True
            else:
                print(" -> 正在检测 PDF 类型...", file=sys.stderr)
                is_scanned = is_scanned_pdf(input_file)
                print(f"    检测结果: {'[扫描版]' if is_scanned else '[电子版]'}", file=sys.stderr)

            if is_scanned:
                conversion_info = process_paddle_ocr(input_file, output_file, args.token)
            else:
                conversion_info = process_pymupdf(input_file, output_file)

        else:
            error_msg = f"❌ 不支持的文件格式: {ext}"
            print(error_msg, file=sys.stderr)
            if args.json_output:
                print(json.dumps({"success": False, "error": error_msg}))
            sys.exit(1)

        # 输出结果
        success_msg = f"✅ 转换成功: {output_file}"
        print(success_msg, file=sys.stderr)

        # JSON格式输出（供程序解析）
        if args.json_output:
            result = {
                "success": True,
                "markdown_file": os.path.abspath(output_file),
                "images_dir": conversion_info.get("images_dir"),
                "image_count": conversion_info.get("image_count", 0),
                "input_file": os.path.abspath(input_file)
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        error_msg = f"❌ 发生未捕获的错误: {e}"
        print(error_msg, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        if args.json_output:
            print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
    finally:
        # 清理临时文件
        if temp_docx and os.path.exists(temp_docx):
            os.remove(temp_docx)
            print(" -> 已清理临时 .docx 文件", file=sys.stderr)

if __name__ == "__main__":
    main()
