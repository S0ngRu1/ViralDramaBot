"""从 frontend/logo.png 生成 Windows 可用的 frontend/logo.ico（多尺寸）。"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "frontend" / "logo.png"
OUT = ROOT / "frontend" / "logo.ico"


def contain_square(img: Image.Image, side: int) -> Image.Image:
    """
    将图按比例缩放到能放进 side×side，居中置于透明背景上。
    避免把非正方形素材硬拉成正方形导致变形、发糊。
    每一层都从原图直接缩放，保证清晰。
    """
    w, h = img.size
    if w <= 0 or h <= 0:
        raise ValueError("invalid image size")
    scale = min(side / w, side / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - nw) // 2
    y = (side - nh) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def main() -> None:
    img = Image.open(SRC).convert("RGBA")

    # Pillow 写 ICO 时单层不得超过 256×256（再大的一层会被丢弃）
    tiers = [16, 24, 32, 48, 64, 128, 256]
    frames = [contain_square(img, s) for s in tiers]

    # 必须以最大的一层作为 save() 的第一参数，否则 Pillow 会用 16×16 判断尺寸，
    # 导致更大分辨率全部被跳过，最终 ICO 里只剩一层。
    frames[-1].save(
        OUT,
        format="ICO",
        sizes=[(t, t) for t in tiers],
        append_images=frames[:-1],
    )
    raw = OUT.read_bytes()[:4]
    assert raw == b"\x00\x00\x01\x00", f"不是合法 ICO 文件头: {raw.hex()}"
    kb = max(OUT.stat().st_size / 1024.0, 0.001)
    print(f"OK: {OUT} ({kb:.1f} KB), 源图 {img.width}×{img.height}, 层: {tiers}")


if __name__ == "__main__":
    main()
