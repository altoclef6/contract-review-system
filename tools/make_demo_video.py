from __future__ import annotations

import json
import os
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".playwright-browsers"))

import imageio.v2 as imageio
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


OUT_DIR = ROOT / "demo_assets"
SHOT_DIR = OUT_DIR / "screenshots"
VIDEO_PATH = OUT_DIR / "contract_review_demo.mp4"
APP_URL = "http://127.0.0.1:8000"
SAMPLE_FILE = ROOT / "samples" / "demo_procurement_contract_risky.docx"
WIDTH = 1600
HEIGHT = 900
FPS = 24


CAPTIONS = [
    (
        "01_api_gate.png",
        "个人 AI 引擎绑定",
        "用户输入 DeepSeek / OpenAI 兼容接口配置后进入审查工作台，密钥仅保存在当前浏览器。",
        3.0,
    ),
    (
        "02_workspace.png",
        "企业级合同审查工作台",
        "多源合同导入、Agent 协同状态、历史记录与审查结果集中在同一工作流内。",
        3.0,
    ),
    (
        "03_uploading.png",
        "多源合同解析",
        "支持 PDF、Word、图片与 OCR；后端将合同文本交给 LangGraph 多智能体流程处理。",
        3.0,
    ),
    (
        "04_result_overview.png",
        "审查结论总览",
        "系统输出风险等级、风险评分、风险数量、修改建议和可导出的报告文件。",
        4.0,
    ),
    (
        "05_risk_board.png",
        "独立风险板块",
        "风险点以卡片归类展示，详情在右侧独立面板展开，避免页面整体突兀拉长。",
        4.0,
    ),
    (
        "06_suggestion_chat.png",
        "AI 修改助理",
        "修改建议以对话式右栏呈现，先给短标题，再按需查看建议条款和修改方向。",
        4.0,
    ),
    (
        "07_knowledge_board.png",
        "法规与内控依据",
        "检索依据按来源合并，展示匹配条数与摘要，便于答辩时说明审查可追溯。",
        4.0,
    ),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for item in candidates:
        if item and Path(item).exists():
            return ImageFont.truetype(item, size=size)
    return ImageFont.load_default()


def require_env() -> dict[str, str]:
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    provider = os.getenv("LLM_PROVIDER") or "deepseek"
    model = os.getenv("LLM_MODEL") or "deepseek-chat"
    base_url = os.getenv("LLM_BASE_URL") or "https://api.deepseek.com/v1"
    if not api_key:
        raise RuntimeError("未在 .env 中找到 LLM_API_KEY，无法录制完整审查流程。")
    return {
        "provider": provider,
        "apiKey": api_key,
        "model": model,
        "baseUrl": base_url,
    }


def capture_screenshots() -> None:
    config = require_env()
    SHOT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1)
        page.goto(APP_URL, wait_until="networkidle")
        page.screenshot(path=SHOT_DIR / "01_api_gate.png", full_page=False)

        page.evaluate(
            """cfg => localStorage.setItem("contract_review_llm_config", JSON.stringify(cfg))""",
            config,
        )
        page.reload(wait_until="networkidle")
        page.screenshot(path=SHOT_DIR / "02_workspace.png", full_page=False)

        page.set_input_files("#contract-file", str(SAMPLE_FILE))
        page.screenshot(path=SHOT_DIR / "03_uploading.png", full_page=False)

        page.click("#submit-btn")
        try:
            page.wait_for_selector(".summary-grid", timeout=180_000)
        except PlaywrightTimeoutError:
            page.wait_for_selector(".history-item", timeout=20_000)
            page.locator(".history-item").first.click()
            page.wait_for_selector(".summary-grid", timeout=30_000)

        page.screenshot(path=SHOT_DIR / "04_result_overview.png", full_page=False)

        risk = page.locator(".risk-card").nth(1)
        if risk.count():
            risk.click()
            page.wait_for_timeout(500)
        page.screenshot(path=SHOT_DIR / "05_risk_board.png", full_page=False)

        suggestion = page.locator(".suggestion-card").nth(1)
        if suggestion.count():
            suggestion.click()
            page.wait_for_timeout(500)
        page.screenshot(path=SHOT_DIR / "06_suggestion_chat.png", full_page=False)

        knowledge = page.locator(".knowledge-card").nth(1)
        if knowledge.count():
            knowledge.click()
            page.wait_for_timeout(500)
        page.screenshot(path=SHOT_DIR / "07_knowledge_board.png", full_page=False)
        browser.close()


def caption_frame(image_path: Path, title: str, subtitle: str) -> Image.Image:
    base = Image.open(image_path).convert("RGB").resize((WIDTH, HEIGHT))
    overlay_h = 150
    overlay = Image.new("RGBA", (WIDTH, overlay_h), (247, 249, 243, 235))
    overlay = overlay.filter(ImageFilter.GaussianBlur(0.2))
    base_rgba = base.convert("RGBA")
    base_rgba.alpha_composite(overlay, (0, HEIGHT - overlay_h))

    draw = ImageDraw.Draw(base_rgba)
    title_font = font(38, bold=True)
    body_font = font(25)
    draw.rounded_rectangle(
        (42, HEIGHT - overlay_h + 28, 56, HEIGHT - 34),
        radius=6,
        fill=(184, 79, 118, 255),
    )
    draw.text((80, HEIGHT - overlay_h + 26), title, fill=(22, 32, 26), font=title_font)
    wrapped = textwrap.fill(subtitle, width=55)
    draw.text((80, HEIGHT - overlay_h + 82), wrapped, fill=(73, 95, 82), font=body_font)
    return base_rgba.convert("RGB")


def hold_frames(frame: Image.Image, seconds: float) -> list[Image.Image]:
    return [frame] * int(seconds * FPS)


def transition_frames(a: Image.Image, b: Image.Image, seconds: float = 0.45) -> list[Image.Image]:
    count = max(1, int(seconds * FPS))
    return [Image.blend(a, b, i / count) for i in range(1, count + 1)]


def build_video() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames: list[Image.Image] = []
    previous: Image.Image | None = None
    for filename, title, subtitle, seconds in CAPTIONS:
        frame = caption_frame(SHOT_DIR / filename, title, subtitle)
        if previous is not None:
            frames.extend(transition_frames(previous, frame))
        frames.extend(hold_frames(frame, seconds))
        previous = frame

    writer = imageio.get_writer(
        VIDEO_PATH,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=16,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame))
    finally:
        writer.close()


def main() -> None:
    start = time.time()
    capture_screenshots()
    build_video()
    print(json.dumps({"video": str(VIDEO_PATH), "seconds": round(time.time() - start, 1)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
