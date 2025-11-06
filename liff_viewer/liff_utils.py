#!/usr/bin/env python3
def expand5(v: int) -> int:
    return (v << 3) | (v >> 2)


def expand6(v: int) -> int:
    return (v << 2) | (v >> 4)


def quantifier_vers_rgb565(r: int, g: int, b: int) -> tuple[int, int, int, int, int, int]:
    r5 = (r * 31 + 127) // 255
    g6 = (g * 63 + 127) // 255
    b5 = (b * 31 + 127) // 255
    r8 = expand5(r5)
    g8 = expand6(g6)
    b8 = expand5(b5)
    return r5, g6, b5, r8, g8, b8