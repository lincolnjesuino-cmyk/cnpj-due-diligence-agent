"""Synthetic payloads shaped like the real APIs. No real company or person data."""

from typing import Any

ESTABLISHED = "11222333000181"  # active, 15 years old, has a company as partner
HOLDING = "44555666000181"  # the partner company above: active, clean
CLOSED = "77888999000181"  # BAIXADA
NEW_TINY = "99888777000100"  # opened recently, symbolic share capital


def brasilapi(
    cnpj: str,
    *,
    name: str,
    status: str = "ATIVA",
    reason: str = "SEM MOTIVO",
    opened: str = "2010-03-15",
    capital: float = 500_000.0,
    cnae: int = 4120400,
    cnae_desc: str = "Construção de edifícios",
    secondary: list[tuple[int, str]] | None = None,
    nature: str = "Sociedade Empresária Limitada",
    partners: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "cnpj": cnpj,
        "razao_social": name,
        "nome_fantasia": "",
        "descricao_situacao_cadastral": status,
        "descricao_motivo_situacao_cadastral": reason,
        "data_situacao_cadastral": "2015-01-01",
        "situacao_especial": "",
        "data_inicio_atividade": opened,
        "natureza_juridica": nature,
        "porte": "DEMAIS",
        "capital_social": capital,
        "cnae_fiscal": cnae,
        "cnae_fiscal_descricao": cnae_desc,
        "cnaes_secundarios": [{"codigo": c, "descricao": d} for c, d in (secondary or [])],
        "municipio": "BARREIRAS",
        "uf": "BA",
        "qsa": partners if partners is not None else [],
    }


def person_partner(name: str) -> dict[str, Any]:
    return {
        "nome_socio": name,
        "qualificacao_socio": "Sócio-Administrador",
        "cnpj_cpf_do_socio": "***123456**",
        "data_entrada_sociedade": "2010-03-15",
    }


def company_partner(name: str, cnpj: str) -> dict[str, Any]:
    return {
        "nome_socio": name,
        "qualificacao_socio": "Sócio",
        "cnpj_cpf_do_socio": cnpj,
        "data_entrada_sociedade": "2012-06-01",
    }


COMPANIES: dict[str, dict[str, Any]] = {
    ESTABLISHED: brasilapi(
        ESTABLISHED,
        name="CONSTRUTORA EXEMPLO LTDA",
        secondary=[(4399103, "Obras de alvenaria"), (7112000, "Serviços de engenharia")],
        partners=[
            person_partner("MARIA EXEMPLO"),
            company_partner("HOLDING EXEMPLO PARTICIPACOES LTDA", HOLDING),
        ],
    ),
    HOLDING: brasilapi(
        HOLDING,
        name="HOLDING EXEMPLO PARTICIPACOES LTDA",
        opened="2008-01-10",
        cnae=6462000,
        cnae_desc="Holdings de instituições não-financeiras",
        partners=[person_partner("JOAO EXEMPLO")],
    ),
    CLOSED: brasilapi(
        CLOSED,
        name="COMERCIO ENCERRADO LTDA",
        status="BAIXADA",
        reason="EXTINCAO POR ENCERRAMENTO LIQUIDACAO VOLUNTARIA",
        cnae=4744099,
        cnae_desc="Comércio varejista de materiais de construção em geral",
        partners=[person_partner("PEDRO EXEMPLO")],
    ),
    NEW_TINY: brasilapi(
        NEW_TINY,
        name="SERVICOS NOVOS LTDA",
        opened="2026-06-01",
        capital=100.0,
        cnae=8211300,
        cnae_desc="Serviços combinados de escritório e apoio administrativo",
        partners=[],
    ),
}


def ceis_item(end: str | None, authority: str = "PREFEITURA MUNICIPAL DE EXEMPLO") -> dict:
    return {
        "tipoSancao": {"descricaoResumida": "Impedimento de licitar e contratar"},
        "orgaoSancionador": {"nome": authority},
        "dataInicioSancao": "01/02/2026",
        "dataFimSancao": end,
        "numeroProcesso": "123/2026",
        "linkPublicacao": "https://example.gov.br/diario/123",
    }
