"""Módulo de ferramentas MCP para cálculo aduaneiro e tributário de importações."""

import logging
from typing import Any, Dict, Optional

try:
    from mcp.server.mcpserver import MCPServer
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore
    except ImportError:
        MCPServer = None  # type: ignore

logger = logging.getLogger(__name__)

# Instância do servidor MCP para registro de ferramentas
mcp_server = MCPServer("scraper-tools") if MCPServer is not None else None
mcp = mcp_server  # Alias de conveniência


def _register_tool(func: Any) -> Any:
    """Registra uma função como ferramenta no servidor MCP se disponível."""
    if mcp_server is not None:
        return mcp_server.tool()(func)
    return func


@_register_tool
def calculate_import_duties(
    price_usd: float,
    shipping_usd: float,
    exchange_rate: float,
    icms_por_dentro: bool = True,
) -> Dict[str, float]:
    """Calcula os tributos de importação para o Brasil (Remessa Conforme / Lei nº 14.902/2024).

    Aplica as alíquotas vigentes do Imposto de Importação (II):
    - Até US$ 50,00 de valor aduaneiro total: 20% sobre o valor aduaneiro.
    - Acima de US$ 50,00: 60% com dedução padrão de US$ 20,00 no imposto devido.
    Adicionalmente, calcula o ICMS com alíquota padrão de 17% (por padrão com cálculo
    'por dentro', conforme Convênio ICMS 81/2023).

    Args:
        price_usd: Preço do produto em dólares americanos (USD).
        shipping_usd: Custo do frete/seguro em dólares americanos (USD).
        exchange_rate: Taxa de câmbio USD para BRL (R$ por US$ 1).
        icms_por_dentro: Se True, aplica a fórmula 'por dentro' do ICMS (padrão legal).
            Se False, aplica cálculo simples ('por fora').

    Returns:
        Dict[str, float]: Dicionário contendo os seguintes valores arredondados em reais (BRL):
            - custo_base_brl: Valor aduaneiro total convertido (produto + frete).
            - imposto_federal_brl: Imposto de Importação federal.
            - icms_brl: ICMS estadual calculado (17%).
            - custo_total_desembarcado_brl: Custo final total (base + impostos).

    Raises:
        ValueError: Se price_usd < 0, shipping_usd < 0 ou exchange_rate <= 0.
    """
    if price_usd < 0:
        raise ValueError("O preço do produto (price_usd) não pode ser negativo.")
    if shipping_usd < 0:
        raise ValueError("O custo de frete (shipping_usd) não pode ser negativo.")
    if exchange_rate <= 0:
        raise ValueError("A taxa de câmbio (exchange_rate) deve ser maior que zero.")

    # 1. Valor Aduaneiro Total (CIF: Preço + Frete)
    total_customs_usd = price_usd + shipping_usd
    custo_base_brl = round(total_customs_usd * exchange_rate, 2)

    # 2. Imposto de Importação (Federal)
    # Regra Remessa Conforme / Lei 14.902/2024:
    # - Até US$ 50: 20%
    # - Acima de US$ 50: 60% com dedução de US$ 20,00
    if total_customs_usd <= 50.0:
        imposto_federal_brl = round(custo_base_brl * 0.20, 2)
    else:
        imposto_federal_usd = max(0.0, (total_customs_usd * 0.60) - 20.0)
        imposto_federal_brl = round(imposto_federal_usd * exchange_rate, 2)

    # 3. ICMS Estadual (17%)
    # No cálculo 'por dentro' (regra padrão nos estados):
    # Base ICMS = (Custo Base BRL + Imposto Federal BRL) / (1 - 0.17)
    # ICMS = Base ICMS * 0.17
    soma_base_e_ii = custo_base_brl + imposto_federal_brl
    if icms_por_dentro:
        base_icms = soma_base_e_ii / (1.0 - 0.17)
        icms_brl = round(base_icms * 0.17, 2)
    else:
        icms_brl = round(soma_base_e_ii * 0.17, 2)

    # 4. Custo Total Desembarcado
    custo_total_desembarcado_brl = round(custo_base_brl + imposto_federal_brl + icms_brl, 2)

    return {
        "custo_base_brl": custo_base_brl,
        "imposto_federal_brl": imposto_federal_brl,
        "icms_brl": icms_brl,
        "custo_total_desembarcado_brl": custo_total_desembarcado_brl,
    }

