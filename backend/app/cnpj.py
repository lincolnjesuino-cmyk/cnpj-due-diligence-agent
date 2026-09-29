"""CNPJ normalization and check-digit validation (Receita Federal algorithm)."""

import re

_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
_WEIGHTS_2 = [6, *_WEIGHTS_1]


class InvalidCNPJError(ValueError):
    pass


def _check_digit(digits: list[int], weights: list[int]) -> int:
    remainder = sum(d * w for d, w in zip(digits, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def normalize(raw: str) -> str:
    """Return the 14-digit CNPJ or raise InvalidCNPJError."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) != 14 or digits == digits[0] * 14:
        raise InvalidCNPJError(f"Invalid CNPJ: {raw!r}")

    numbers = [int(c) for c in digits]
    if _check_digit(numbers[:12], _WEIGHTS_1) != numbers[12]:
        raise InvalidCNPJError(f"Invalid CNPJ (check digit): {raw!r}")
    if _check_digit(numbers[:13], _WEIGHTS_2) != numbers[13]:
        raise InvalidCNPJError(f"Invalid CNPJ (check digit): {raw!r}")
    return digits


def format_cnpj(digits: str) -> str:
    d = normalize(digits)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def is_cnpj(value: str) -> bool:
    try:
        normalize(value)
    except InvalidCNPJError:
        return False
    return True
