import pathlib
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# ========== Парсинг чисел/строк ==========

def parse_int(raw: str) -> int:
    cleaned = raw.strip().rstrip(",")
    return int(cleaned, 0)

def normalize_curve_type(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.strip().lower())

def build_modulus(exponents_line: str) -> int:
    exponents = [parse_int(token) for token in exponents_line.split()]
    if not exponents:
        raise ValueError("Reduction polynomial exponents are required for GF(2^m)")
    modulus = 0
    for power in exponents:
        if power < 0:
            raise ValueError("Polynomial exponents must be non-negative")
        modulus |= 1 << power
    return modulus

def extract_points(line: str) -> List[Tuple[int, int]]:
    points: List[Tuple[int, int]] = []
    for raw_point in re.findall(r"\(([^)]+)\)", line):
        x_raw, y_raw = raw_point.split(",")
        points.append((parse_int(x_raw), parse_int(y_raw)))
    return points

def extract_scalar(line: str) -> int:
    no_points = re.sub(r"\([^)]*\)", " ", line)
    match = re.search(r"(-?0x[0-9a-fA-F]+|-?0b[01]+|-?\d+)", no_points)
    if not match:
        raise ValueError(f"Cannot find scalar in line: {line}")
    return parse_int(match.group(1))

def parse_ab(rest_lines: List[str]) -> Tuple[int, int, int]:
    """
    Считывает коэффициенты a и b.
    По ТЗ они в одной строке: 'a b'. Но поддерживается и вариант двумя строками.
    Возвращает (a, b, consumed_lines_count).
    """
    if not rest_lines:
        raise ValueError("Missing curve coefficients line(s)")

    tokens = rest_lines[0].split()
    if len(tokens) >= 2:
        a = parse_int(tokens[0])
        b = parse_int(tokens[1])
        return a, b, 1

    if len(rest_lines) < 2:
        raise ValueError("Curve coefficients require 2 numbers (a and b)")
    a = parse_int(rest_lines[0])
    b = parse_int(rest_lines[1])
    return a, b, 2

# ========== Поля ==========

@dataclass
class PrimeField:
    p: int

    def add(self, a: int, b: int) -> int:
        return (a + b) % self.p

    def sub(self, a: int, b: int) -> int:
        return (a - b) % self.p

    def mul(self, a: int, b: int) -> int:
        return (a * b) % self.p

    def inv(self, a: int) -> int:
        if a % self.p == 0:
            raise ZeroDivisionError("Inverse of zero does not exist")
        return pow(a, self.p - 2, self.p)

    def div(self, a: int, b: int) -> int:
        return self.mul(a, self.inv(b))

    def neg(self, a: int) -> int:
        return (-a) % self.p

    def square(self, a: int) -> int:
        return self.mul(a, a)

@dataclass
class BinaryField:
    modulus: int

    @property
    def degree(self) -> int:
        return self.modulus.bit_length() - 1

    def reduce(self, value: int) -> int:
        mod_deg = self.degree
        while value.bit_length() - 1 >= mod_deg:
            shift = value.bit_length() - 1 - mod_deg
            value ^= self.modulus << shift
        return value

    def add(self, a: int, b: int) -> int:
        return a ^ b

    def sub(self, a: int, b: int) -> int:
        return self.add(a, b)

    def mul(self, a: int, b: int) -> int:
        result = 0
        aa, bb = a, b
        while bb:
            if bb & 1:
                result ^= aa
            bb >>= 1
            aa <<= 1
            if aa >> self.degree:
                aa ^= self.modulus
        return self.reduce(result)

    def square(self, a: int) -> int:
        return self.mul(a, a)

    def inv(self, a: int) -> int:
        if a == 0:
            raise ZeroDivisionError("Inverse of zero does not exist")
        # расширенный алгоритм Евклида для полиномов над GF(2)
        u, v = a, self.modulus
        g1, g2 = 1, 0
        while u != 1:
            j = u.bit_length() - v.bit_length()
            if j < 0:
                u, v = v, u
                g1, g2 = g2, g1
                j = -j
            u ^= v << j
            g1 ^= g2 << j
        return self.reduce(g1)

    def div(self, a: int, b: int) -> int:
        return self.mul(a, self.inv(b))

    def neg(self, a: int) -> int:
        return a

Point = Optional[Tuple[int, int]]

# ========== Кривые ==========

class PrimeCurve:
    # y^2 = x^3 + a x + b  над Fp
    def __init__(self, field: PrimeField, a: int, b: int):
        self.f = field
        self.a = a % field.p
        self.b = b % field.p

    def add(self, p1: Point, p2: Point) -> Point:
        if p1 is None:
            return p2
        if p2 is None:
            return p1
        x1, y1 = p1
        x2, y2 = p2
        if x1 == x2:
            if (y1 + y2) % self.f.p == 0:
                return None
            return self.double(p1)

        lam = self.f.div(self.f.sub(y2, y1), self.f.sub(x2, x1))
        x3 = self.f.sub(self.f.sub(self.f.square(lam), x1), x2)
        y3 = self.f.sub(self.f.mul(lam, self.f.sub(x1, x3)), y1)
        return x3, y3

    def double(self, p: Point) -> Point:
        if p is None:
            return None
        x1, y1 = p
        if y1 % self.f.p == 0:
            return None
        lam = self.f.div(self.f.add(self.f.mul(3, self.f.square(x1)), self.a), self.f.mul(2, y1))
        x3 = self.f.sub(self.f.square(lam), self.f.mul(2, x1))
        y3 = self.f.sub(self.f.mul(lam, self.f.sub(x1, x3)), y1)
        return x3, y3

    def multiply(self, p: Point, n: int) -> Point:
        if n < 0:
            raise ValueError("Negative scalars are not supported in this assignment")
        result: Point = None
        addend = p
        k = n
        while k > 0:
            if k & 1:
                result = self.add(result, addend)
            addend = self.double(addend)
            k >>= 1
        return result

class BinaryCurve:
    # y^2 + x y = x^3 + a x^2 + b over GF(2^m)
    def __init__(self, field: BinaryField, a: int, b: int):
        self.f = field
        self.a = field.reduce(a)
        self.b = field.reduce(b)

    def add(self, p1: Point, p2: Point) -> Point:
        if p1 is None:
            return p2
        if p2 is None:
            return p1
        x1, y1 = p1
        x2, y2 = p2

        if x1 == x2:
            if self.f.add(y1, y2) == x1:
                return None
            if y1 == y2:
                return self.double(p1)
            raise ZeroDivisionError("Points have identical x but are not inverses or equal")

        lam = self.f.div(self.f.add(y1, y2), self.f.add(x1, x2))
        x3 = self.f.add(self.f.add(self.f.add(self.f.square(lam), lam), x1), self.f.add(x2, self.a))
        y3 = self.f.add(self.f.mul(self.f.add(x1, x3), lam), self.f.add(x3, y1))
        return self.f.reduce(x3), self.f.reduce(y3)

    def double(self, p: Point) -> Point:
        if p is None:
            return None
        x1, y1 = p
        if x1 == 0:
            return None
        lam = self.f.add(x1, self.f.div(y1, x1))
        x3 = self.f.add(self.f.add(self.f.square(lam), lam), self.a)
        y3 = self.f.add(self.f.mul(self.f.add(x1, x3), lam), self.f.add(x3, y1))
        return self.f.reduce(x3), self.f.reduce(y3)

    def multiply(self, p: Point, n: int) -> Point:
        if n < 0:
            raise ValueError("Negative scalars are not supported in this assignment")
        result: Point = None
        addend = p
        k = n
        while k > 0:
            if k & 1:
                result = self.add(result, addend)
            addend = self.double(addend)
            k >>= 1
        return result

# ========== Парсинг входа/задач ==========

def parse_curve(lines: List[str]):
    t = normalize_curve_type(lines[0])

    # 1) Prime field (тип 1)
    if t in {"1", "zp", "fp", "prime", "zpp", "zpc"} or ("zp" in t):
        p = parse_int(lines[1])
        a, b, consumed = parse_ab(lines[2:])
        tasks_start = 2 + consumed
        return PrimeCurve(PrimeField(p), a, b), lines[tasks_start:]

    # 2) Binary field (типы 2/3 и любые GF(2^m)-подобные записи)
    is_binary = (
        t in {"2", "3", "gf2s", "gf2ns", "gf2", "gf2n"}  # <-- добавили gf2n
        or ("gf2" in t)                                  # <-- ловит gf(2^m), gf2t, gf2m и т.п.
        or (t.startswith("gf") and "2" in t)             # <-- на всякий случай
    )

    if is_binary:
        modulus = build_modulus(lines[1])
        a, b, consumed = parse_ab(lines[2:])
        tasks_start = 2 + consumed
        return BinaryCurve(BinaryField(modulus), a, b), lines[tasks_start:]

    raise ValueError(f"Unknown curve type in line 1: {lines[0]!r}")


def format_point(point: Point) -> str:
    if point is None:
        return "0"
    x, y = point
    return f"({x}, {y})"

def handle_task(curve, line: str) -> str:
    op = line.strip().lower()

    if op.startswith("a"):
        pts = extract_points(line)
        if len(pts) != 2:
            raise ValueError(f"Addition task requires two points: {line}")
        left = f"{format_point(pts[0])} + {format_point(pts[1])}"
        res = curve.add(pts[0], pts[1])
        return f"{left} = {format_point(res)}"

    if op.startswith("m"):
        pts = extract_points(line)
        if len(pts) != 1:
            raise ValueError(f"Multiplication task requires one point: {line}")
        scalar = extract_scalar(line)
        left = f"{format_point(pts[0])} * {scalar}"
        res = curve.multiply(pts[0], scalar)
        return f"{left} = {format_point(res)}"

    raise ValueError(f"Unknown task (must start with A or M): {line}")



def process_file(path: pathlib.Path, output_dir: pathlib.Path) -> pathlib.Path:
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) < 4:
        raise ValueError(f"Not enough data in {path.name} (need at least 4 non-empty lines)")

    curve, tasks = parse_curve(lines)
    results = [handle_task(curve, task) for task in tasks]

    out_name = f"{path.stem}_OUTPUT{path.suffix}"
    out_path = output_dir / out_name
    out_path.write_text("\n".join(results), encoding="utf-8")
    return out_path

def main():
    base = pathlib.Path(__file__).resolve().parent
    input_dir = base / "INPUT"
    output_dir = base / "OUTPUT"
    output_dir.mkdir(exist_ok=True)

    for input_file in sorted(input_dir.glob("*.txt")):
        process_file(input_file, output_dir)

if __name__ == "__main__":
    main()
