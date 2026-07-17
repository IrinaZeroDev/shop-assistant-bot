"""Генерирует Welcome-картинку бота (640x360 PNG) — та же палитра и персонаж,
что и в аватарке (assets/generate_avatar.py), но в сцене: пакет с покупками
и рядом — карточка товара и чек/статус доставки, чтобы сразу считывалась
суть бота (магазин + заказы), а не только приветствие.

Требует Pillow:
    pip install pillow
    python assets/generate_welcome.py

Результат: assets/bot_welcome.png — загрузить вручную через @BotFather
→ /mybots → Edit Bot → Edit Welcome Message → Edit Welcome Picture,
отправить файл как «Фото» (не как файл/документ).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from generate_avatar import CHARCOAL, CORAL, CORAL_DEEP, CREAM_BG, GOLD, WHITE

WIDTH, HEIGHT = 640, 360


def _card(draw: ImageDraw.ImageDraw, box: list[int], accent) -> None:
    draw.rounded_rectangle(box, radius=16, fill=WHITE)
    x0, y0, x1, y1 = box
    pad = 16
    draw.rounded_rectangle([x0 + pad, y0 + pad, x1 - pad, y0 + pad + 26], radius=8, fill=accent)
    line_y = y0 + pad + 26 + 14
    for i in range(3):
        w = (x1 - x0 - 2 * pad) * (0.9 if i < 2 else 0.55)
        draw.rounded_rectangle(
            [x0 + pad, line_y + i * 18, x0 + pad + w, line_y + i * 18 + 8],
            radius=4,
            fill=(226, 221, 217),
        )


def generate(output_path: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), CREAM_BG)
    draw = ImageDraw.Draw(img)

    draw.ellipse([40, 300, 300, 340], fill=(247, 224, 206))

    cx = 175
    draw.arc([cx - 50, 130, cx + 50 - 100 + 100, 260], start=180, end=360, fill=CORAL_DEEP, width=14)
    draw.arc([cx - 10, 130, cx + 90, 260], start=180, end=360, fill=CORAL_DEEP, width=14)

    draw.polygon(
        [(cx - 90, 230), (cx + 90, 230), (cx + 112, 330), (cx - 112, 330)],
        fill=CORAL,
    )
    draw.polygon(
        [(cx - 90, 230), (cx - 60, 230), (cx - 72, 330), (cx - 112, 330)],
        fill=CORAL_DEEP,
    )

    eye_y = 255
    draw.ellipse([cx - 40, eye_y, cx - 8, eye_y + 32], fill=WHITE)
    draw.ellipse([cx + 8, eye_y, cx + 40, eye_y + 32], fill=WHITE)
    draw.ellipse([cx - 32, eye_y + 8, cx - 16, eye_y + 24], fill=CHARCOAL)
    draw.ellipse([cx + 16, eye_y + 8, cx + 32, eye_y + 24], fill=CHARCOAL)
    draw.arc([cx - 26, 288, cx + 26, 330], start=20, end=160, fill=WHITE, width=8)

    star_cx, star_cy, r = cx + 65, 145, 22
    draw.ellipse([star_cx - r, star_cy - r, star_cx + r, star_cy + r], fill=GOLD)
    draw.ellipse([star_cx - 6, star_cy - 6, star_cx + 6, star_cy + 6], fill=WHITE)

    _card(draw, [400, 55, 600, 165], CORAL)
    _card(draw, [400, 190, 600, 300], (120, 190, 150))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Сохранено: {output_path} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    generate(Path(__file__).parent / "bot_welcome.png")
