"""Testes de integração para o pipeline principal (main.py)."""

import uuid
from unittest.mock import AsyncMock, patch
import chromadb
import pytest

from main import (
    DEFAULT_EXCHANGE_RATE,
    MOCK_NOLAN_ITEMS,
    fetch_items,
    format_search_result,
    main,
    parse_shipping_usd,
    run_pipeline,
)
from src.rag.vector_store import BlurayVectorStore
from src.scraper.client import EbayScraper, EbayScraperError


@pytest.fixture
def isolated_vector_store() -> BlurayVectorStore:
    """Fixture que fornece um BlurayVectorStore com cliente efêmero isolado."""
    client = chromadb.EphemeralClient()
    col_name = f"test_pipeline_{uuid.uuid4().hex[:8]}"
    return BlurayVectorStore(collection_name=col_name, client=client)


def test_parse_shipping_usd() -> None:
    """Valida a conversão de textos de frete para float em USD."""
    assert parse_shipping_usd("Free shipping") == 0.0
    assert parse_shipping_usd("Frete grátis") == 0.0
    assert parse_shipping_usd("US $4.99") == 4.99
    assert parse_shipping_usd("US $12.50") == 12.50
    assert parse_shipping_usd("$3.00") == 3.00
    assert parse_shipping_usd("") == 0.0
    assert parse_shipping_usd("invalid text") == 0.0


@pytest.mark.asyncio
async def test_fetch_items_with_mocked_scraper() -> None:
    """Valida busca de itens com scraper mockado."""
    mock_items = [
        {"title": "Item 1", "price": 25.0, "currency": "USD", "shipping": "Free shipping", "url": "http://test1"},
        {"title": "Item 2", "price": 30.0, "currency": "USD", "shipping": "US $5.00", "url": "http://test2"},
    ]

    mock_scraper = AsyncMock(spec=EbayScraper)
    mock_scraper.search_bluray = AsyncMock(return_value=mock_items)

    items = await fetch_items(scraper=mock_scraper, search_term="Christopher Nolan 4K", max_results=2)
    assert len(items) == 2
    assert items[0]["title"] == "Item 1"
    mock_scraper.search_bluray.assert_awaited_once_with(query="Christopher Nolan 4K", max_results=2)


@pytest.mark.asyncio
async def test_fetch_items_fallback_on_network_error() -> None:
    """Valida fallback para dados mockados em caso de falha de rede."""
    mock_scraper = AsyncMock(spec=EbayScraper)
    mock_scraper.search_bluray = AsyncMock(side_effect=EbayScraperError("Network Timeout"))

    items = await fetch_items(
        scraper=mock_scraper,
        search_term="Christopher Nolan 4K",
        max_results=3,
        use_mock_fallback=True,
    )
    assert len(items) == 3
    assert items[0]["title"] == MOCK_NOLAN_ITEMS[0]["title"]


@pytest.mark.asyncio
async def test_run_pipeline_full_integration(isolated_vector_store: BlurayVectorStore) -> None:
    """Valida o pipeline completo mockando apenas o scraper de rede."""
    mock_catalog = [
        {
            "title": "Oppenheimer 4K Ultra HD Blu-ray Christopher Nolan",
            "price": 30.00,
            "currency": "USD",
            "shipping": "US $5.00",
            "url": "https://www.ebay.com/itm/oppenheimer",
        },
        {
            "title": "Interstellar 4K UHD Blu-ray Sci-Fi Space Nolan",
            "price": 20.00,
            "currency": "USD",
            "shipping": "Free shipping",
            "url": "https://www.ebay.com/itm/interstellar",
        },
        {
            "title": "Dunkirk 4K UHD Blu-ray War History Nolan",
            "price": 15.00,
            "currency": "USD",
            "shipping": "US $4.00",
            "url": "https://www.ebay.com/itm/dunkirk",
        },
    ]

    mock_scraper = AsyncMock(spec=EbayScraper)
    mock_scraper.search_bluray = AsyncMock(return_value=mock_catalog)

    # Executa pipeline: busca semântica por física quântica e bomba atômica
    result = await run_pipeline(
        search_term="Christopher Nolan 4K",
        exchange_rate=5.50,
        semantic_query="filme sobre física quântica e bomba atômica",
        vector_store=isolated_vector_store,
        scraper=mock_scraper,
        max_results=3,
    )

    assert result is not None
    assert "Oppenheimer" in result["title"]
    assert result["metadata"]["preco_original"] == 30.00
    assert result["metadata"]["moeda_original"] == "USD"

    # Verificação matemática do imposto aduaneiro (30 + 5 = 35 USD <= 50 USD, câmbio 5.50):
    # Custo base = 35 * 5.50 = 192.50
    # II (20%) = 38.50
    # ICMS = (192.50 + 38.50) / 0.83 * 0.17 = 231 / 0.83 * 0.17 = 47.31
    # Custo desembarcado = 192.50 + 38.50 + 47.31 = 278.31
    assert result["preco_brl_desembarcado"] == 278.31
    assert isolated_vector_store.count() == 3


@pytest.mark.asyncio
async def test_run_pipeline_empty_items(isolated_vector_store: BlurayVectorStore) -> None:
    """Valida retorno None quando nenhum item é encontrado e fallback desabilitado."""
    mock_scraper = AsyncMock(spec=EbayScraper)
    mock_scraper.search_bluray = AsyncMock(return_value=[])

    result = await run_pipeline(
        scraper=mock_scraper,
        vector_store=isolated_vector_store,
        use_mock_fallback=False,
    )
    assert result is None


def test_format_search_result() -> None:
    """Valida a formatação de saída para o terminal."""
    sample_result = {
        "title": "Oppenheimer 4K UHD",
        "preco_brl_desembarcado": 262.33,
        "distance": 0.8523,
        "metadata": {
            "title": "Oppenheimer 4K UHD",
            "preco_original": 27.99,
            "moeda_original": "USD",
            "custo_total_desembarcado_brl": 262.33,
        },
    }

    formatted = format_search_result(sample_result)
    assert "Oppenheimer 4K UHD" in formatted
    assert "USD 27.99" in formatted
    assert "R$ 262.33" in formatted
    assert "Pontuação/Relevância:" in formatted
    assert "Distância Vetorial: 0.8523" in formatted


def test_main_cli_execution(capsys: pytest.CaptureFixture[str]) -> None:
    """Valida execução completa da função main() através da CLI."""
    with patch("main.fetch_items", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = MOCK_NOLAN_ITEMS[:2]

        main()

        captured = capsys.readouterr()
        assert "RESULTADO DA BUSCA SEMÂNTICA (RAG)" in captured.out
        assert "Título:" in captured.out
        assert "Preço Original:" in captured.out
        assert "Custo Desembarcado em R$:" in captured.out
        assert "Pontuação/Relevância:" in captured.out

