import httpx
import pytest
import respx

from app.sources import (
    BRASILAPI_URL,
    TRANSPARENCIA_URL,
    CompanyNotFoundError,
    PublicDataClient,
    SourceUnavailableError,
)
from tests.fixtures import COMPANIES, ESTABLISHED, HOLDING, ceis_item


@respx.mock
async def test_company_is_parsed_and_source_recorded() -> None:
    respx.get(BRASILAPI_URL.format(cnpj=ESTABLISHED)).respond(json=COMPANIES[ESTABLISHED])
    async with httpx.AsyncClient() as http:
        client = PublicDataClient(http, transparencia_key=None)
        profile = await client.company("11.222.333/0001-81")

    assert profile.legal_name == "CONSTRUTORA EXEMPLO LTDA"
    assert profile.status == "ATIVA"
    assert [p.is_company for p in profile.partners] == [False, True]
    assert profile.partners[1].document == HOLDING
    assert len(client.consulted) == 1


@respx.mock
async def test_company_not_found() -> None:
    respx.get(BRASILAPI_URL.format(cnpj=ESTABLISHED)).respond(status_code=404)
    async with httpx.AsyncClient() as http:
        with pytest.raises(CompanyNotFoundError):
            await PublicDataClient(http, None).company(ESTABLISHED)


@respx.mock
async def test_company_source_down() -> None:
    respx.get(BRASILAPI_URL.format(cnpj=ESTABLISHED)).mock(side_effect=httpx.ConnectTimeout("x"))
    async with httpx.AsyncClient() as http:
        with pytest.raises(SourceUnavailableError):
            await PublicDataClient(http, None).company(ESTABLISHED)


async def test_sanctions_without_key_are_reported_as_unchecked() -> None:
    async with httpx.AsyncClient() as http:
        result = await PublicDataClient(http, None).sanctions(ESTABLISHED)
    assert result.checked is False
    assert result.note


@respx.mock
async def test_sanctions_query_both_registries_with_key_header() -> None:
    ceis = respx.get(TRANSPARENCIA_URL.format(registry="ceis")).respond(json=[ceis_item(None)])
    cnep = respx.get(TRANSPARENCIA_URL.format(registry="cnep")).respond(json=[])
    async with httpx.AsyncClient() as http:
        result = await PublicDataClient(http, "test-key").sanctions(ESTABLISHED)

    assert result.checked
    assert [s.registry for s in result.sanctions] == ["CEIS"]
    assert result.sanctions[0].end is None
    request = ceis.calls.last.request
    assert request.headers["chave-api-dados"] == "test-key"
    assert request.url.params["codigoSancionado"] == ESTABLISHED
    assert cnep.called


@respx.mock
async def test_sanctions_source_error_degrades_to_unchecked() -> None:
    respx.get(TRANSPARENCIA_URL.format(registry="ceis")).respond(status_code=503)
    async with httpx.AsyncClient() as http:
        result = await PublicDataClient(http, "test-key").sanctions(ESTABLISHED)
    assert result.checked is False
    assert "CEIS" in (result.note or "")
