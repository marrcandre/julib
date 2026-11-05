"""Generate a synthetic EAN-13 camera stream using only the standard library."""

import sys
from pathlib import Path


def generate(destination: Path) -> None:
    # Standard EAN-13 encoding, known valid ISBN: O Hobbit, 9780261102217.
    left = [
        "0001101",
        "0011001",
        "0010011",
        "0111101",
        "0100011",
        "0110001",
        "0101111",
        "0111011",
        "0110111",
        "0001011",
    ]
    alternate = [
        "0100111",
        "0110011",
        "0011011",
        "0100001",
        "0011101",
        "0111001",
        "0000101",
        "0010001",
        "0001001",
        "0010111",
    ]
    isbn = "9780261102217"
    bits = "101" + "".join(
        (left if kind == "L" else alternate)[int(digit)]
        for kind, digit in zip("LGGLGL", isbn[1:7], strict=True)
    )
    bits += (
        "01010"
        + "".join(
            "".join("1" if bit == "0" else "0" for bit in left[int(digit)])
            for digit in isbn[7:]
        )
        + "101"
    )
    width, height = 640, 480
    luminance = bytearray([235]) * (width * height)
    for i, bit in enumerate(bits):
        if bit == "1":
            for y in range(100, 360):
                start = y * width + 130 + i * 4
                luminance[start : start + 4] = bytes([16]) * 4
    frame = bytes(luminance) + bytes([128]) * (width * height // 2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        output.write(b"YUV4MPEG2 W640 H480 F5:1 Ip A1:1 C420jpeg\n")
        for _ in range(10):
            output.write(b"FRAME\n" + frame)


if __name__ == "__main__":
    generate(Path(sys.argv[1]))
