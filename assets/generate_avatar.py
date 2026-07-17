"""Генерирует аватарку бота: дружелюбный пакет с покупками — минималистичный
образ ассистента интернет-магазина. Тёплая коралловая палитра — намеренно
отличается от синей/бирюзовой первого бота (sale_chart-bot), чтобы у ботов
были разные узнаваемые образы.

Требует Pillow (dev-инструмент, не рантайм-зависимость бота):
    pip install pillow
    python assets/generate_avatar.py

Результат: assets/bot_avatar.png (640x360 — формат, который требует
@BotFather для /setuserpic). Bot API не позволяет боту установить себе
аватар программно — загружать вручную через @BotFather → /mybots →
Edit Bot → Edit Botpic → отправить как «Фото» (не как файл).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
CORAL = (255, 106, 74)
CORAL_DEEP = (214, 76, 48)
CREAM_BG = (255, 240, 227)
CHARCOAL = (43, 38, 41)
WHITE = (255, 255, 255)
GOLD = (255, 190, 92)

BOTFATHER_SIZE = (640, 360)


def _draw_square() -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), WHITE)
    draw = ImageDraw.Draw(img)

    margin = 12
    draw.ellipse([margin, margin, SIZE - margin, SIZE - margin], fill=CREAM_BG)

    # Ручки пакета — две дуги
    draw.arc([150, 90, 250, 220], start=180, end=360, fill=CORAL_DEEP, width=16)
    draw.arc([262, 90, 362, 220], start=180, end=360, fill=CORAL_DEEP, width=16)

    # Тело пакета — трапеция (шире снизу)
    draw.polygon(
        [(120, 190), (392, 190), (420, 430), (92, 430)],
        fill=CORAL,
    )
    # Складка/тень сбоку для объёма
    draw.polygon([(120, 190), (150, 190), (140, 430), (92, 430)], fill=CORAL_DEEP)

    # Глаза
    eye_y = 270
    draw.ellipse([190, eye_y, 234, eye_y + 44], fill=WHITE)
    draw.ellipse([290, eye_y, 334, eye_y + 44], fill=WHITE)
    draw.ellipse([204, eye_y + 12, 228, eye_y + 36], fill=CHARCOAL)
    draw.ellipse([304, eye_y + 12, 328, eye_y + 36], fill=CHARCOAL)

    # Улыбка
    draw.arc([210, 320, 310, 390], start=20, end=160, fill=WHITE, width=12)

    # Бирка/звёздочка сверху справа — акцент "покупки"
    star_cx, star_cy, r = 400, 130, 34
    draw.ellipse([star_cx - r, star_cy - r, star_cx + r, star_cy + r], fill=GOLD)
    draw.ellipse([star_cx - 8, star_cy - 8, star_cx + 8, star_cy + 8], fill=WHITE)

    return img


def generate(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    square = _draw_square()

    square_path = output_dir / "bot_avatar_square.png"
    square.save(square_path, "PNG")
    print(f"Сохранено: {square_path}")

    width, height = BOTFATHER_SIZE
    scaled = square.resize((height, height), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), WHITE)
    canvas.paste(scaled, ((width - height) // 2, 0))

    wide_path = output_dir / "bot_avatar.png"
    canvas.save(wide_path, "PNG")
    print(f"Сохранено: {wide_path} ({width}x{height}) — этот файл для @BotFather")


if __name__ == "__main__":
    generate(Path(__file__).parent)
