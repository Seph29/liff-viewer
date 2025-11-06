#!/usr/bin/env python3
import struct
from pathlib import Path
from PIL import Image

MAGIC_LIFF = b"liff"
MAGIC_LIFF_ALT = b"LIFF"
END_MARKER = b"\x00" * 7 + b"\x01"
CHANNEL_RGBA = 0xA2


def lire_liff(chemin: Path) -> tuple[int, int, int, memoryview]:
    data = chemin.read_bytes()
    
    if data[:4] not in (MAGIC_LIFF, MAGIC_LIFF_ALT):
        raise ValueError(f"Mauvaise magic dans {chemin}: {data[:4]!r}")

    width = struct.unpack(">I", data[4:8])[0]
    height = struct.unpack(">I", data[8:12])[0]
    channels = data[12]

    payload = memoryview(data[13:-8]) if data.endswith(END_MARKER) else memoryview(data[13:])
    return int(width), int(height), channels, payload


def liff_hash(px: list[int]) -> int:
    r, g, b, a = px
    return (r * 7 + g * 5 + b * 3) & 0x3F


def decoder_liff_vers_rgba(chemin: Path) -> tuple[int, int, bytes]:
    def score_coherence_lignes(buf: bytes, w: int, h: int) -> int:
        s = 0
        for y in range(h):
            base = y * w * 4
            r0, g0, b0 = buf[base+0], buf[base+1], buf[base+2]
            for x in range(1, w):
                o = base + 4*x
                r1, g1, b1 = buf[o+0], buf[o+1], buf[o+2]
                s += abs(r1 - r0) + abs(g1 - g0) + abs(b1 - b0)
                r0, g0, b0 = r1, g1, b1
        return s

    def vers_colonne_majeure(buf: bytes, w: int, h: int) -> bytes:
        out = bytearray(len(buf))
        i = 0
        for x in range(w):
            for y in range(h):
                src = i * 4
                dst = (y * w + x) * 4
                out[dst:dst+4] = buf[src:src+4]
                i += 1
        return bytes(out)

    w, h, channels, s = lire_liff(chemin)
    
    if channels != CHANNEL_RGBA:
        raise ValueError(f"Canaux LIFF inattendus: 0x{channels:02X} (attendu 0x{CHANNEL_RGBA:02X})")

    total_pixels = w * h
    out = bytearray(total_pixels * 4)
    index = [[0, 0, 0, 0] for _ in range(64)]

    r = g = b = 0
    a = 255
    p = 0
    run = 0
    n = len(s)

    for px_idx in range(total_pixels):
        if run > 0:
            run -= 1
        elif p < n:
            b1 = s[p]
            p += 1

            if b1 == 0xFE:
                if p + 1 > n:
                    break
                byte1 = s[p]
                p += 1
                b = byte1 & 0x1F
                g = (byte1 >> 5) & 0x07
                byte2 = s[p]
                p += 1
                r = (byte2 >> 3) & 0x1F
                g |= (byte2 << 3) & 0x3F

            elif b1 == 0xFF:
                if p + 2 > n:
                    break
                byte1 = s[p]
                p += 1
                b = byte1 & 0x1F
                g = (byte1 >> 5) & 0x07
                byte2 = s[p]
                p += 1
                r = (byte2 >> 3) & 0x1F
                g |= (byte2 << 3) & 0x3F
                a = s[p]
                p += 1

            else:
                tag = b1 & 0xC0

                if tag == 0x00:
                    idx = b1 & 0x3F
                    r, g, b, a = index[idx]

                elif tag == 0x40:
                    db = ((b1 >> 4) & 0x03) - 2
                    dg = ((b1 >> 2) & 0x03) - 2
                    dr = (b1 & 0x03) - 2
                    r = (r + dr) % 32
                    g = (g + dg) % 64
                    b = (b + db) % 32

                elif tag == 0x80:
                    if p >= n:
                        break
                    b2 = s[p]
                    p += 1
                    vg = (b1 & 0x3F) - 32
                    b = (b + vg - 8 + ((b2 >> 4) & 0x0F)) % 32
                    g = (g + vg) % 64
                    r = (r + vg - 8 + (b2 & 0x0F)) % 32

                else:
                    run = b1 & 0x3F

        idx_hash = liff_hash([r, g, b, a])
        index[idx_hash] = [r, g, b, a]

        off = px_idx * 4
        out[off + 0] = (r * 256) // 32
        out[off + 1] = (g * 256) // 64
        out[off + 2] = (b * 256) // 32
        out[off + 3] = a

    buf_ligne = bytes(out)
    est_icone = (max(w, h) <= 64)

    if est_icone:
        final = buf_ligne
    else:
        buf_col = vers_colonne_majeure(buf_ligne, w, h)
        score_ligne = score_coherence_lignes(buf_ligne, w, h)
        score_col = score_coherence_lignes(buf_col, w, h)
        amelioration = (score_ligne - score_col) / max(1, score_ligne)
        
        if (h > w) and (amelioration >= 0.12):
            final = buf_col
        else:
            final = buf_ligne

    return w, h, final


def encoder_rgba_vers_liff_bytes(img: Image.Image) -> bytes:
    img = img.convert("RGBA")
    w, h = img.size
    pixels = list(img.getdata())
    total = len(pixels)

    index = [[0, 0, 0, 0] for _ in range(64)]
    pr, pg, pb, pa = 0, 0, 0, 255
    run = 0
    out = bytearray()

    for pos, (r8, g8, b8, a) in enumerate(pixels):
        r5 = (r8 * 31 + 127) // 255
        g6 = (g8 * 63 + 127) // 255
        b5 = (b8 * 31 + 127) // 255
        px_q = [r5, g6, b5, a]

        if px_q == [pr, pg, pb, pa]:
            run += 1
            if run == 62 or pos == total - 1:
                out.append(0xC0 | (run - 1))
                run = 0
            continue

        if run > 0:
            out.append(0xC0 | (run - 1))
            run = 0

        idx = (r5 * 7 + g6 * 5 + b5 * 3) & 0x3F
        if index[idx] == px_q:
            out.append(idx & 0x3F)
        else:
            dr = r5 - pr
            dg = g6 - pg
            db = b5 - pb
            encode = False

            if (-2 <= dr <= 1) and (-2 <= dg <= 1) and (-2 <= db <= 1) and a == pa:
                b0 = 0x40
                b0 |= (db + 2) << 4
                b0 |= (dg + 2) << 2
                b0 |= (dr + 2)
                out.append(b0)
                encode = True
            else:
                dg_l = dg
                dr_dg = dr - dg_l
                db_dg = db - dg_l
                if (-32 <= dg_l <= 31) and (-8 <= dr_dg <= 7) and (-8 <= db_dg <= 7) and a == pa:
                    b0 = 0x80 | (dg_l + 32)
                    b1 = ((db_dg + 8) << 4) | ((dr_dg + 8) & 0x0F)
                    out.extend((b0, b1))
                    encode = True

            if not encode:
                u16 = (r5 << 11) | (g6 << 5) | b5
                b1 = u16 & 0xFF
                b2 = (u16 >> 8) & 0xFF
                if a == pa:
                    out.extend((0xFE, b1, b2))
                else:
                    out.extend((0xFF, b1, b2, a))

            index[idx] = px_q.copy()

        pr, pg, pb, pa = r5, g6, b5, a

    if run > 0:
        out.append(0xC0 | (run - 1))

    header = MAGIC_LIFF + struct.pack(">I", w) + struct.pack(">I", h) + bytes([CHANNEL_RGBA])
    out.extend(END_MARKER)
    return header + out


def encoder_fichier_image_vers_liff(chemin_entree: Path, chemin_sortie: Path):
    img = Image.open(chemin_entree).convert("RGBA")
    data = encoder_rgba_vers_liff_bytes(img)
    chemin_sortie.write_bytes(data)