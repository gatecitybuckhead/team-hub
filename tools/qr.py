"""
Tiny dependency-free QR Code generator (byte mode, error-correction level M).
Standard library only, so it runs offline on the Mac Mini.

Supports versions 1-6 (up to ~100 bytes) — far more than a LAN URL needs.
Public API:  qr_svg(data)  ->  SVG string (black modules on white, with quiet zone)
"""

# ---- Galois field GF(256) with primitive polynomial 0x11d ----
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gmul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n):
    g = [1]
    for i in range(n):
        # multiply g by (x - alpha^i)  == (x + alpha^i) in GF(2)
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= _gmul(c, _EXP[i])
        g = ng
    return g


def _rs_ec(data, n):
    gen = _rs_generator(n)
    msg = list(data) + [0] * n
    for i in range(len(data)):
        coef = msg[i]
        if coef != 0:
            for j in range(1, len(gen)):
                msg[i + j] ^= _gmul(gen[j], coef)
    return msg[len(data):]


# ---- Version parameters for EC level M ----
# version: (size, [alignment centers], num_blocks, data_codewords_per_block, ec_codewords_per_block)
_VERSIONS = {
    1: (21, [],        1, 16, 10),
    2: (25, [6, 18],   1, 28, 16),
    3: (29, [6, 22],   1, 44, 26),
    4: (33, [6, 26],   2, 32, 18),
    5: (37, [6, 30],   2, 43, 24),
    6: (41, [6, 34],   4, 27, 16),
}


def _choose_version(nbytes):
    # bytes available = num_blocks * data_per_block, minus 2 overhead (mode nibble + 8-bit count)
    for v in range(1, 7):
        _, _, nb, dpb, _ = _VERSIONS[v]
        capacity = nb * dpb - 2  # 4-bit mode + 8-bit count == 12 bits ~ handled below precisely
        if nbytes <= capacity:
            return v
    raise ValueError("data too long for supported QR versions (max ~100 bytes)")


def _encode_data(data_bytes, version):
    _, _, nb, dpb, _ = _VERSIONS[version]
    total_data_cw = nb * dpb
    bits = []

    def put(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)              # byte mode
    put(len(data_bytes), 8)     # char count (8 bits for versions 1-9)
    for b in data_bytes:
        put(b, 8)

    # terminator
    cap_bits = total_data_cw * 8
    for _ in range(min(4, cap_bits - len(bits))):
        bits.append(0)
    # pad to byte boundary
    while len(bits) % 8 != 0:
        bits.append(0)
    # to codewords
    cw = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]
    # pad bytes
    pads = [0xEC, 0x11]
    i = 0
    while len(cw) < total_data_cw:
        cw.append(pads[i % 2])
        i += 1
    return cw


def _build_codewords(data_cw, version):
    _, _, nb, dpb, ecpb = _VERSIONS[version]
    blocks = [data_cw[i * dpb:(i + 1) * dpb] for i in range(nb)]
    ec_blocks = [_rs_ec(b, ecpb) for b in blocks]
    # interleave data
    result = []
    for i in range(dpb):
        for b in blocks:
            result.append(b[i])
    for i in range(ecpb):
        for e in ec_blocks:
            result.append(e[i])
    return result


# ---- Matrix construction ----
def _new_matrix(size):
    return [[None] * size for _ in range(size)]


def _place_finder(m, r, c):
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(m) and 0 <= cc < len(m):
                if 0 <= dr <= 6 and 0 <= dc <= 6:
                    on = (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4))
                    m[rr][cc] = 1 if on else 0
                else:
                    m[rr][cc] = 0  # separator


def _place_alignment(m, centers):
    size = len(m)
    for r in centers:
        for c in centers:
            # skip if overlaps a finder
            if (r <= 7 and c <= 7) or (r <= 7 and c >= size - 8) or (r >= size - 8 and c <= 7):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    on = (dr in (-2, 2) or dc in (-2, 2) or (dr == 0 and dc == 0))
                    m[r + dr][c + dc] = 1 if on else 0


def _reserve_format(m):
    size = len(m)
    # format info areas set to a sentinel (-1) so data skips them; filled later
    for i in range(9):
        if m[8][i] is None:
            m[8][i] = -1
        if m[i][8] is None:
            m[i][8] = -1
    for i in range(8):
        if m[8][size - 1 - i] is None:
            m[8][size - 1 - i] = -1
        if m[size - 1 - i][8] is None:
            m[size - 1 - i][8] = -1


def _matrix_skeleton(version):
    size, centers, _, _, _ = _VERSIONS[version]
    m = _new_matrix(size)
    _place_finder(m, 0, 0)
    _place_finder(m, 0, size - 7)
    _place_finder(m, size - 7, 0)
    # timing patterns
    for i in range(size):
        if m[6][i] is None:
            m[6][i] = 1 if i % 2 == 0 else 0
        if m[i][6] is None:
            m[i][6] = 1 if i % 2 == 0 else 0
    _place_alignment(m, centers)
    # dark module
    m[size - 8][8] = 1
    _reserve_format(m)
    return m


def _place_data(m, codewords):
    """Zigzag symbol-character placement per ISO/IEC 18004 7.7.3 (matches spec)."""
    size = len(m)
    bits = []
    for cw in codewords:
        for i in range(7, -1, -1):
            bits.append((cw >> i) & 1)
    idx = 0
    for right in range(size - 1, 0, -2):
        if right <= 6:
            right -= 1  # skip the vertical timing column
        for vertical in range(size):
            for z in range(2):
                j = right - z
                upwards = (right & 2) == 0
                upwards ^= (j < 6)
                i = (size - 1 - vertical) if upwards else vertical
                if m[i][j] is None:  # empty data module
                    m[i][j] = bits[idx] if idx < len(bits) else 0
                    idx += 1


_MASKS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def _is_function(skel, r, c):
    return skel[r][c] is not None


def _apply_mask(data_matrix, skel, mask_fn):
    size = len(data_matrix)
    out = [row[:] for row in data_matrix]
    for r in range(size):
        for c in range(size):
            if not _is_function(skel, r, c) and mask_fn(r, c):
                out[r][c] ^= 1
    return out


_FORMAT_GEN = 0b10100110111


def _format_bits(mask_index):
    # EC level M -> 0b00
    data = (0b00 << 3) | mask_index
    rem = data << 10
    while rem.bit_length() - 1 >= 10:
        rem ^= _FORMAT_GEN << (rem.bit_length() - 1 - 10)
    bits = ((data << 10) | rem) ^ 0b101010000010010
    return bits  # 15 bits, bit 14 = MSB


def _place_format(m, mask_index):
    """Format info placement per ISO/IEC 18004 7.9 (matches spec)."""
    fmt = _format_bits(mask_index)
    row8 = m[8]
    voffset = 0
    hoffset = 0
    for i in range(8):
        vbit = (fmt >> i) & 1          # LSB-first up the left column / down bottom-left
        hbit = (fmt >> (14 - i)) & 1   # MSB-first along row 8
        if i == 6:                     # jump the timing pattern
            voffset += 1
            hoffset = 1
        m[i + voffset][8] = vbit       # vertical, upper-left
        row8[i + hoffset] = hbit       # horizontal, upper-left
        row8[-1 - i] = vbit            # horizontal, upper-right
        m[-1 - i][8] = hbit            # vertical, bottom-left
    m[-8][8] = 1                       # dark module


def _penalty(m):
    size = len(m)
    score = 0
    # rule 1: runs of >=5
    for line in list(m) + [list(col) for col in zip(*m)]:
        run = 1
        for i in range(1, size):
            if line[i] == line[i - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    # rule 2: 2x2 blocks
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    # rule 3: finder-like patterns
    pat1 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    pat2 = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1]
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(size - 10):
            seg = line[i:i + 11]
            if seg == pat1 or seg == pat2:
                score += 40
    # rule 4: deviation of dark-module ratio from 50%
    dark = sum(sum(row) for row in m)
    ratio = dark * 100 / (size * size)
    score += (abs(int(ratio) - 50) // 5) * 10
    return score


def make_matrix(data):
    if isinstance(data, str):
        data_bytes = data.encode("latin-1")
    else:
        data_bytes = bytes(data)
    version = _choose_version(len(data_bytes))
    # bump version if precise bit capacity is exceeded
    while True:
        try:
            data_cw = _encode_data(data_bytes, version)
            break
        except Exception:
            version += 1
    codewords = _build_codewords(data_cw, version)
    skel = _matrix_skeleton(version)
    data_matrix = [row[:] for row in skel]
    # convert sentinels: -1 (format reserve) treated as function/no-data, None -> data
    _place_data(data_matrix, codewords)
    # normalize: any remaining None -> 0, -1 -> 0 for now (format placed later)
    size = len(data_matrix)
    for r in range(size):
        for c in range(size):
            if data_matrix[r][c] is None or data_matrix[r][c] == -1:
                data_matrix[r][c] = 0

    # function-module map for masking (True where NOT maskable)
    func = [[skel[r][c] is not None for c in range(size)] for r in range(size)]

    best = None
    for mi in range(8):
        masked = [row[:] for row in data_matrix]
        for r in range(size):
            for c in range(size):
                if not func[r][c] and _MASKS[mi](r, c):
                    masked[r][c] ^= 1
        _place_format(masked, mi)
        pen = _penalty(masked)
        if best is None or pen < best[0]:
            best = (pen, masked)
    return best[1]


def qr_svg(data, box=8, border=4, dark="#000000", light="#ffffff"):
    m = make_matrix(data)
    size = len(m)
    dim = (size + border * 2) * box
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{dim}" height="{dim}" '
        f'viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges">',
        f'<rect width="{dim}" height="{dim}" fill="{light}"/>',
    ]
    for r in range(size):
        for c in range(size):
            if m[r][c]:
                x = (c + border) * box
                y = (r + border) * box
                parts.append(f'<rect x="{x}" y="{y}" width="{box}" height="{box}" fill="{dark}"/>')
    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    import sys
    print(qr_svg(sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.50:8080"))
