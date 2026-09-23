"""Testes unitários para as ferramentas MCP e cálculo de tributos de importação."""

import json
import pytest
from src.mcp_server.tools import calculate_import_duties, mcp_server


def test_calculate_import_duties_below_50_usd() -> None:
    """Valida o cálculo de tributos para compras de até US$ 50,00 (alíquota II de 20%)."""
    price_usd = 30.0
    shipping_usd = 10.0
    exchange_rate = 5.0

    result = calculate_import_duties(
        price_usd=price_usd,
        shipping_usd=shipping_usd,
        exchange_rate=exchange_rate,
    )

    # Valor aduaneiro: (30 + 10) * 5.0 = R$ 200,00
    assert result["custo_base_brl"] == 200.00

    # Imposto Federal: 20% sobre R$ 200,00 = R$ 40,00
    assert result["imposto_federal_brl"] == 40.00

    # ICMS por dentro: (200 + 40) / 0.83 * 0.17 = 240 / 0.83 * 0.17 = 49.16
    assert result["icms_brl"] == 49.16

    # Custo Total Desembarcado: 200 + 40 + 49.16 = 289.16
    assert result["custo_total_desembarcado_brl"] == 289.16


def test_calculate_import_duties_exact_50_usd_boundary() -> None:
    """Valida o limite exato de US$ 50,00 na transição de alíquota."""
    price_usd = 40.0
    shipping_usd = 10.0
    exchange_rate = 5.0

    result = calculate_import_duties(
        price_usd=price_usd,
        shipping_usd=shipping_usd,
        exchange_rate=exchange_rate,
    )

    # 50 USD * 5.0 = 250.00
    assert result["custo_base_brl"] == 250.00
    # 20% de 250.00 = 50.00
    assert result["imposto_federal_brl"] == 50.00
    # (250 + 50) / 0.83 * 0.17 = 300 / 0.83 * 0.17 = 61.45
    assert result["icms_brl"] == 61.45
    assert result["custo_total_desembarcado_brl"] == 361.45


def test_calculate_import_duties_above_50_usd() -> None:
    """Valida o cálculo de tributos para compras acima de US$ 50,00 (60% com dedução de US$ 20)."""
    price_usd = 80.0
    shipping_usd = 20.0
    exchange_rate = 5.20

    result = calculate_import_duties(
        price_usd=price_usd,
        shipping_usd=shipping_usd,
        exchange_rate=exchange_rate,
    )

    # Valor aduaneiro: (80 + 20) * 5.20 = 100 * 5.20 = R$ 520,00
    assert result["custo_base_brl"] == 520.00

    # Imposto Federal: (100 * 0.60 - 20) * 5.20 = 40 * 5.20 = R$ 208,00
    assert result["imposto_federal_brl"] == 208.00

    # ICMS por dentro: (520 + 208) / 0.83 * 0.17 = 728 / 0.83 * 0.17 = 149.11
    assert result["icms_brl"] == 149.11

    # Custo Total Desembarcado: 520 + 208 + 149.11 = 877.11
    assert result["custo_total_desembarcado_brl"] == 877.11


def test_calculate_import_duties_free_shipping() -> None:
    """Valida compra com frete grátis (shipping_usd = 0.0)."""
    result = calculate_import_duties(price_usd=25.0, shipping_usd=0.0, exchange_rate=5.0)

    assert result["custo_base_brl"] == 125.00
    assert result["imposto_federal_brl"] == 25.00
    # (125 + 25) / 0.83 * 0.17 = 150 / 0.83 * 0.17 = 30.72
    assert result["icms_brl"] == 30.72
    assert result["custo_total_desembarcado_brl"] == 180.72


def test_calculate_import_duties_icms_por_fora() -> None:
    """Valida o cálculo quando o ICMS é configurado para cálculo simples ('por fora')."""
    result = calculate_import_duties(
        price_usd=30.0,
        shipping_usd=10.0,
        exchange_rate=5.0,
        icms_por_dentro=False,
    )

    assert result["custo_base_brl"] == 200.00
    assert result["imposto_federal_brl"] == 40.00
    # (200 + 40) * 0.17 = 40.80
    assert result["icms_brl"] == 40.80
    assert result["custo_total_desembarcado_brl"] == 280.80


@pytest.mark.parametrize(
    "price,shipping,exchange,err_msg",
    [
        (-1.0, 10.0, 5.0, "O preço do produto (price_usd) não pode ser negativo."),
        (10.0, -5.0, 5.0, "O custo de frete (shipping_usd) não pode ser negativo."),
        (10.0, 5.0, 0.0, "A taxa de câmbio (exchange_rate) deve ser maior que zero."),
        (10.0, 5.0, -2.0, "A taxa de câmbio (exchange_rate) deve ser maior que zero."),
    ],
)
def test_calculate_import_duties_invalid_inputs(
    price: float, shipping: float, exchange: float, err_msg: str
) -> None:
    """Valida que entradas negativas ou inválidas disparam ValueError."""
    with pytest.raises(ValueError) as exc_info:
        calculate_import_duties(price_usd=price, shipping_usd=shipping, exchange_rate=exchange)
    assert err_msg in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_server_tool_registration_and_execution() -> None:
    """Valida que a ferramenta está devidamente registrada e executável no servidor MCP."""
    assert mcp_server is not None

    tools = await mcp_server.list_tools()
    tool_names = [tool.name for tool in tools]
    assert "calculate_import_duties" in tool_names

    # Execução via protocolo MCP
    call_result = await mcp_server.call_tool(
        "calculate_import_duties",
        {"price_usd": 30.0, "shipping_usd": 10.0, "exchange_rate": 5.0},
    )

    assert not call_result.is_error
    assert len(call_result.content) > 0
    parsed_content = json.loads(call_result.content[0].text)
    assert parsed_content["custo_base_brl"] == 200.00
    assert parsed_content["imposto_federal_brl"] == 40.00
    assert parsed_content["icms_brl"] == 49.16
    assert parsed_content["custo_total_desembarcado_brl"] == 289.16
