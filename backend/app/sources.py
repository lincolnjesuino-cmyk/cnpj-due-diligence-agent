"""Clients for public Brazilian government data sources."""

from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.cnpj import normalize
from app.models import CompanyProfile, Partner, Sanction, SanctionsResult, SourceRef

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
TRANSPARENCIA_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/{registry}"


class SourceUnavailableError(RuntimeError):
    pass


class CompanyNotFoundError(LookupError):
    pass


def _date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_brasilapi(data: dict[str, Any]) -> CompanyProfile:
    partners = [
        Partner(
            name=p.get("nome_socio") or "",
            role=p.get("qualificacao_socio"),
            document=(p.get("cnpj_cpf_do_socio") or None),
            since=_date(p.get("data_entrada_sociedade")),
        )
        for p in data.get("qsa") or []
    ]
    return CompanyProfile(
        cnpj=str(data["cnpj"]).zfill(14),
        legal_name=data.get("razao_social") or "",
        trade_name=data.get("nome_fantasia") or None,
        status=(data.get("descricao_situacao_cadastral") or "DESCONHECIDA").upper(),
        status_reason=data.get("descricao_motivo_situacao_cadastral") or None,
        status_date=_date(data.get("data_situacao_cadastral")),
        special_situation=data.get("situacao_especial") or None,
        opened_on=_date(data.get("data_inicio_atividade")),
        legal_nature=data.get("natureza_juridica"),
        size=data.get("porte"),
        share_capital=data.get("capital_social"),
        main_activity_code=data.get("cnae_fiscal"),
        main_activity=data.get("cnae_fiscal_descricao"),
        secondary_activities=[
            f"{c.get('codigo')} - {c.get('descricao')}"
            for c in data.get("cnaes_secundarios") or []
            if c.get("codigo")
        ],
        city=data.get("municipio"),
        state=data.get("uf"),
        partners=partners,
    )


def parse_sanction(registry: str, item: dict[str, Any]) -> Sanction:
    return Sanction(
        registry=registry.upper(),
        sanction_type=(item.get("tipoSancao") or {}).get("descricaoResumida"),
        authority=(item.get("orgaoSancionador") or {}).get("nome"),
        start=_date(item.get("dataInicioSancao")),
        end=_date(item.get("dataFimSancao")),
        process_number=item.get("numeroProcesso"),
        link=item.get("linkPublicacao") or None,
    )


class PublicDataClient:
    """Fetches and normalizes data; records every source it consulted."""

    def __init__(self, http: httpx.AsyncClient, transparencia_key: str | None) -> None:
        self._http = http
        self._transparencia_key = transparencia_key
        self.consulted: list[SourceRef] = []

    async def company(self, cnpj: str) -> CompanyProfile:
        digits = normalize(cnpj)
        url = BRASILAPI_URL.format(cnpj=digits)
        try:
            response = await self._http.get(url)
        except httpx.HTTPError as exc:
            raise SourceUnavailableError(f"BrasilAPI unavailable: {exc}") from exc
        if response.status_code == 404:
            raise CompanyNotFoundError(f"CNPJ {digits} not found in the Receita Federal registry.")
        if response.status_code >= 400:
            raise SourceUnavailableError(f"BrasilAPI returned HTTP {response.status_code}.")
        self.consulted.append(
            SourceRef(name="Receita Federal (via BrasilAPI)", url=url, consulted_at=_now())
        )
        return parse_brasilapi(response.json())

    async def sanctions(self, cnpj: str) -> SanctionsResult:
        digits = normalize(cnpj)
        if not self._transparencia_key:
            return SanctionsResult(
                checked=False,
                note="Portal da Transparência API key not configured; CEIS/CNEP not checked.",
            )

        found: list[Sanction] = []
        for registry in ("ceis", "cnep"):
            url = TRANSPARENCIA_URL.format(registry=registry)
            try:
                response = await self._http.get(
                    url,
                    params={"codigoSancionado": digits, "pagina": 1},
                    headers={"chave-api-dados": self._transparencia_key},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                return SanctionsResult(
                    checked=False,
                    note=f"Portal da Transparência unavailable ({registry.upper()}): {exc}",
                )
            self.consulted.append(
                SourceRef(
                    name=f"Portal da Transparência — {registry.upper()}",
                    url=f"{url}?codigoSancionado={digits}",
                    consulted_at=_now(),
                )
            )
            found.extend(parse_sanction(registry, item) for item in response.json())
        return SanctionsResult(checked=True, sanctions=found)
