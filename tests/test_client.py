"""Testes unitários para o módulo client (EbayScraper)."""

import httpx
import pytest
import respx

from src.scraper.client import (
    DEFAULT_HEADERS,
    EbayScraper,
    EbayScraperError,
    EbayScraperHTTPError,
    EbayScraperTimeoutError,
)

MOCK_SEARCH_RESULTS_HTML = """
<!DOCTYPE html>
<html lang="en">
<body>
<ul class="srp-results srp-list">
    <!-- Item dummy frequentemente injetado pelo eBay no topo -->
    <li class="s-item">
        <div class="s-item__info">
            <div class="s-item__title">Shop on eBay</div>
            <span class="s-item__price">$10.00</span>
        </div>
    </li>
    <!-- Item 1: Oppenheimer -->
    <li class="s-item">
        <div class="s-item__info">
            <a class="s-item__link" href="https://www.ebay.com/itm/111">
                <h3 class="s-item__title">
                    <span role="heading">Oppenheimer [New 4K Ultra HD Blu-ray]</span>
                </h3>
            </a>
            <span class="s-item__price">US $27.99</span>
            <span class="s-item__shipping">Free shipping</span>
        </div>
    </li>
    <!-- Item 2: Dune: Part Two -->
    <li class="s-item">
        <div class="s-item__info">
            <a class="s-item__link" href="https://www.ebay.com/itm/222">
                <h3 class="s-item__title">Dune: Part Two (Blu-ray + Digital)</h3>
            </a>
            <span class="s-item__price">$34.50</span>
            <span class="s-item__logisticsCost">US $4.99 Standard Shipping</span>
        </div>
    </li>
    <!-- Item 3: The Dark Knight Trilogy -->
    <li class="s-item">
        <div class="s-item__info">
            <a class="s-item__link" href="https://www.ebay.com/itm/333">
                <h3 class="s-item__title">The Dark Knight Trilogy [Blu-ray]</h3>
            </a>
            <span class="s-item__price">EUR 19.95</span>
            <span class="s-item__shipping">EUR 3.50 International Shipping</span>
        </div>
    </li>
    <!-- Item 4: Interstellar -->
    <li class="s-item">
        <div class="s-item__info">
            <a class="s-item__link" href="https://www.ebay.com/itm/444">
                <h3 class="s-item__title">Interstellar Blu-ray Steelbook</h3>
            </a>
            <span class="s-item__price">US $22.00</span>
            <span class="s-item__shipping">Free shipping</span>
        </div>
    </li>
    <!-- Item 5: Inception -->
    <li class="s-item">
        <div class="s-item__info">
            <a class="s-item__link" href="https://www.ebay.com/itm/555">
                <h3 class="s-item__title">Inception 4K UHD Blu-ray</h3>
            </a>
            <span class="s-item__price">$18.50</span>
            <span class="s-item__shipping">US $3.00 Shipping</span>
        </div>
    </li>
    <!-- Item 6: Tenet -->
    <li class="s-item">
        <div class="s-item__info">
            <a class="s-item__link" href="https://www.ebay.com/itm/666">
                <h3 class="s-item__title">Tenet Blu-ray 4K Ultra HD</h3>
            </a>
            <span class="s-item__price">$15.00</span>
            <span class="s-item__shipping">Free shipping</span>
        </div>
    </li>
</ul>
</body>
</html>
"""


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_success_and_headers():
    """Valida busca com sucesso, extração dos campos e envio de headers de navegador."""
    route = respx.get("https://www.ebay.com/sch/i.html").respond(
        status_code=200,
        text=MOCK_SEARCH_RESULTS_HTML,
    )

    scraper = EbayScraper()
    results = await scraper.search_bluray(query="Oppenheimer", max_results=2)

    assert route.called
    sent_request = route.calls.last.request

    # Valida cabeçalhos simulando navegador real
    assert "User-Agent" in sent_request.headers
    assert "Mozilla" in sent_request.headers["User-Agent"]
    assert "Chrome" in sent_request.headers["User-Agent"]

    # Valida query params com adição de termo blu-ray
    assert "_nkw" in sent_request.url.params
    assert "Oppenheimer blu-ray" == sent_request.url.params["_nkw"]

    # Valida quantidade e integridade dos resultados
    assert len(results) == 2

    first = results[0]
    assert first["title"] == "Oppenheimer [New 4K Ultra HD Blu-ray]"
    assert first["price"] == 27.99
    assert first["currency"] == "USD"
    assert first["shipping"] == "Free shipping"
    assert first["url"] == "https://www.ebay.com/itm/111"

    second = results[1]
    assert second["title"] == "Dune: Part Two (Blu-ray + Digital)"
    assert second["price"] == 34.50
    assert second["currency"] == "USD"
    assert second["shipping"] == "US $4.99 Standard Shipping"
    assert second["url"] == "https://www.ebay.com/itm/222"


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_does_not_duplicate_bluray_term():
    """Valida que a busca não duplica o termo blu-ray se já estiver na query."""
    route = respx.get("https://www.ebay.com/sch/i.html").respond(
        status_code=200,
        text=MOCK_SEARCH_RESULTS_HTML,
    )

    scraper = EbayScraper()
    await scraper.search_bluray(query="Dune Blu-ray", max_results=1)

    assert route.called
    assert route.calls.last.request.url.params["_nkw"] == "Dune Blu-ray"


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_respects_max_results():
    """Valida que o scraper respeita o limite de max_results (padrão 5)."""
    respx.get("https://www.ebay.com/sch/i.html").respond(
        status_code=200,
        text=MOCK_SEARCH_RESULTS_HTML,
    )

    scraper = EbayScraper()
    # O mock contém 6 itens válidos + 1 dummy, o padrão deve retornar 5
    results = await scraper.search_bluray(query="Christopher Nolan")
    assert len(results) == 5


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_empty_html_results():
    """Valida retorno de lista vazia quando nenhum produto for encontrado."""
    empty_html = "<html><body><div class='no-results'>Nenhum resultado</div></body></html>"
    respx.get("https://www.ebay.com/sch/i.html").respond(
        status_code=200,
        text=empty_html,
    )

    scraper = EbayScraper()
    results = await scraper.search_bluray(query="FilmeInexistenteXYZ123")
    assert results == []


@pytest.mark.asyncio
async def test_search_bluray_zero_or_negative_max_results():
    """Valida que max_results <= 0 retorna lista vazia imediatamente sem chamada de rede."""
    scraper = EbayScraper()
    assert await scraper.search_bluray("Matrix", max_results=0) == []
    assert await scraper.search_bluray("Matrix", max_results=-3) == []


@pytest.mark.asyncio
async def test_search_bluray_empty_query_raises_value_error():
    """Valida que query vazia levanta ValueError."""
    scraper = EbayScraper()
    with pytest.raises(ValueError, match="não pode ser vazia"):
        await scraper.search_bluray("")

    with pytest.raises(ValueError, match="não pode ser vazia"):
        await scraper.search_bluray("   ")


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_timeout_exception():
    """Valida tratamento e lançamento de EbayScraperTimeoutError em caso de timeout."""
    respx.get("https://www.ebay.com/sch/i.html").mock(
        side_effect=httpx.ReadTimeout("Tempo limite de leitura excedido.")
    )

    scraper = EbayScraper()
    with pytest.raises(EbayScraperTimeoutError, match="Timeout ao consultar o eBay"):
        await scraper.search_bluray(query="Interstellar")


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_http_status_error_500():
    """Valida tratamento e lançamento de EbayScraperHTTPError em status 500."""
    respx.get("https://www.ebay.com/sch/i.html").respond(status_code=500)

    scraper = EbayScraper()
    with pytest.raises(EbayScraperHTTPError) as exc_info:
        await scraper.search_bluray(query="Oppenheimer")

    assert exc_info.value.status_code == 500
    assert "Erro HTTP 500" in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_http_status_error_404():
    """Valida tratamento e lançamento de EbayScraperHTTPError em status 404."""
    respx.get("https://www.ebay.com/sch/i.html").respond(status_code=404)

    scraper = EbayScraper()
    with pytest.raises(EbayScraperHTTPError) as exc_info:
        await scraper.search_bluray(query="Oppenheimer")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_network_error():
    """Valida tratamento e lançamento de EbayScraperError em erro de conexão de rede."""
    respx.get("https://www.ebay.com/sch/i.html").mock(
        side_effect=httpx.ConnectError("Falha na resolução DNS ou conexão recusada.")
    )

    scraper = EbayScraper()
    with pytest.raises(EbayScraperError, match="Erro de conexão/rede"):
        await scraper.search_bluray(query="Gladiator")


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_with_context_manager():
    """Valida uso do EbayScraper como async context manager."""
    respx.get("https://www.ebay.com/sch/i.html").respond(
        status_code=200,
        text=MOCK_SEARCH_RESULTS_HTML,
    )

    async with EbayScraper() as scraper:
        results = await scraper.search_bluray(query="Dune", max_results=1)
        assert len(results) == 1
        assert results[0]["title"] == "Oppenheimer [New 4K Ultra HD Blu-ray]"


@pytest.mark.asyncio
@respx.mock
async def test_search_bluray_with_custom_client():
    """Valida que uma instância customizada de AsyncClient pode ser injetada."""
    respx.get("https://www.ebay.com/sch/i.html").respond(
        status_code=200,
        text=MOCK_SEARCH_RESULTS_HTML,
    )

    custom_headers = {"User-Agent": "CustomTestBot/1.0"}
    async with httpx.AsyncClient(headers=custom_headers) as client:
        scraper = EbayScraper(client=client, headers=custom_headers)
        results = await scraper.search_bluray(query="Avatar", max_results=1)
        assert len(results) == 1
