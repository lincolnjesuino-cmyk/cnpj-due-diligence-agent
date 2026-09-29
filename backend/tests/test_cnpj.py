import pytest

from app.cnpj import InvalidCNPJError, format_cnpj, is_cnpj, normalize


@pytest.mark.parametrize(
    "raw",
    ["33.000.167/0001-01", "33000167000101", " 33.000.167/0001-01 "],
)
def test_normalize_accepts_formatted_and_raw(raw: str) -> None:
    assert normalize(raw) == "33000167000101"


@pytest.mark.parametrize(
    "raw",
    ["", "123", "33000167000102", "11111111111111", "abc", "330001670001011"],
)
def test_normalize_rejects_invalid(raw: str) -> None:
    with pytest.raises(InvalidCNPJError):
        normalize(raw)


def test_format() -> None:
    assert format_cnpj("33000167000101") == "33.000.167/0001-01"


def test_is_cnpj() -> None:
    assert is_cnpj("47.960.950/0001-21")
    assert not is_cnpj("47.960.950/0001-22")
