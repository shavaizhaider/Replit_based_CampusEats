"""Generate simple raster PWA icons using only Python's standard library."""

import math
import struct
import zlib
from pathlib import Path


def png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def draw_icon(size: int, output: Path) -> None:
    scale = size / 512
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            px, py = x / scale, y / scale
            color = (36, 77, 61, 255)
            distance = math.hypot(px - 256, py - 258)
            if distance <= 174:
                color = (244, 240, 230, 255)
            if 148 <= px <= 364 and 252 <= py <= 370 and py >= 252 + abs(px - 256) * 0.10:
                color = (255, 253, 248, 255)
            if ((px - 256) / 108) ** 2 + ((py - 252) / 25) ** 2 <= 1:
                color = (217, 95, 67, 255)
            if (px - 218) ** 2 + (py - 244) ** 2 <= 18**2:
                color = (243, 191, 99, 255)
            if (px - 270) ** 2 + (py - 238) ** 2 <= 16**2:
                color = (91, 126, 80, 255)
            if 184 <= py <= 202 and 168 <= px <= 344:
                color = (36, 77, 61, 255)
            row.extend(color)
        rows.append(bytes(row))

    raw = b"".join(rows)
    header = struct.pack(">2I5B", size, size, 8, 6, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", header)
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)


if __name__ == "__main__":
    image_dir = Path(__file__).resolve().parents[1] / "app" / "static" / "images"
    draw_icon(192, image_dir / "icon-192.png")
    draw_icon(512, image_dir / "icon-512.png")
