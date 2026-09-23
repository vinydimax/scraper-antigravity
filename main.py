"""Script principal integrando todo o pipeline:

1. Scraping de itens de Blu-ray (EbayScraper).
2. Cálculo de tributos aduaneiros de importação (calculate_import_duties).
3. Indexação vetorial e metadados estruturados no ChromaDB (BlurayVectorStore).
4. Busca semântica e exibição formatada do resultado no terminal.
"""

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from src.scraper.client import EbayScraper, EbayScraperError
from src.scraper.parser import _extract_price_and_currency
from src.mcp_server.tools import calculate_import_duties
from src.rag.vector_store import BlurayVectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_SEARCH_TERM: str = "Christopher Nolan 4K"
DEFAULT_EXCHANGE_RATE: float = 5.50
DEFAULT_SEMANTIC_QUERY: str = "filme sobre física quântica e bomba atômica"

# Conjunto de dados de fallback/mock para garantir execução offline e testes determinísticos
MOCK_NOLAN_ITEMS: List[Dict[str, Any]] = [
    {
        "title": "Oppenheimer 4K Ultra HD Blu-ray Christopher Nolan",
        "price": 27.99,
        "currency": "USD",
        "shipping": "US $5.00",
        "url": "https://www.ebay.com/itm/111111111111",
    },
    {
        "title": "Interstellar 4K UHD Blu-ray Sci-Fi Space Christopher Nolan",
        "price": 22.50,
        "currency": "USD",
        "shipping": "Free shipping",
        "url": "https://www.ebay.com/itm/222222222222",
    },
    {
        "title": "The Dark Knight 4K Ultra HD Blu-ray Batman Christian Bale Nolan",
        "price": 19.99,
        "currency": "USD",
        "shipping": "US $4.50",
        "url": "https://www.ebay.com/itm/333333333333",
    },
    {
        "title": "Inception 4K Ultra HD Blu-ray Leonardo DiCaprio Nolan",
        "price": 21.00,
        "currency": "USD",
        "shipping": "Free shipping",
        "url": "https://www.ebay.com/itm/444444444444",
    },
    {
        "title": "Dunkirk 4K Ultra HD Blu-ray World War II Christopher Nolan",
        "price": 18.50,
        "currency": "USD",
        "shipping": "US $3.99",
        "url": "https://www.ebay.com/itm/555555555555",
    },
]


def parse_shipping_usd(shipping_raw: str) -> float:
    """Extrai o valor numérico do frete em USD a partir de texto.

    Args:
        shipping_raw: String contendo informação de frete (ex: 'US $4.99', 'Free shipping').

    Returns:
        float: Custo do frete em USD (0.0 caso gratuito ou não identificado).
    """
    if not shipping_raw or "free" in shipping_raw.lower() or "grátis" in shipping_raw.lower():
        return 0.0

    try:
        price, _ = _extract_price_and_currency(shipping_raw)
        return float(price)
    except Exception:
        return 0.0


async def fetch_items(
    scraper: Optional[EbayScraper] = None,
    search_term: str = DEFAULT_SEARCH_TERM,
    max_results: int = 5,
    use_mock_fallback: bool = True,
) -> List[Dict[str, Any]]:
    """Busca itens no eBay utilizando o scraper, aplicando fallback de mock se necessário."""
    scraper_instance = scraper or EbayScraper()
    items: List[Dict[str, Any]] = []

    try:
        logger.info("Iniciando busca no eBay para o termo: '%s'...", search_term)
        items = await scraper_instance.search_bluray(query=search_term, max_results=max_results)
    except (EbayScraperError, Exception) as exc:
        logger.warning("Não foi possível obter dados online do eBay (%s).", exc)

    if not items and use_mock_fallback:
        logger.info("Utilizando itens mockados de fallback para '%s'.", search_term)
        items = MOCK_NOLAN_ITEMS[:max_results]

    return items


def format_search_result(result: Dict[str, Any]) -> str:
    """Formata o resultado mais relevante da busca semântica para exibição no terminal."""
    meta = result.get("metadata", {})
    title = result.get("title") or meta.get("title", "Desconhecido")
    original_price = meta.get("preco_original", 0.0)
    currency = meta.get("moeda_original", "USD")
    custo_desembarcado = result.get("preco_brl_desembarcado") or meta.get("custo_total_desembarcado_brl", 0.0)
    distance = result.get("distance")

    if distance is not None:
        score = 1.0 / (1.0 + distance)
        relevance_str = f"{score:.4f} (Distância Vetorial: {distance:.4f})"
    else:
        relevance_str = "N/A"

    return (
        "\n"
        "======================================================================\n"
        "                RESULTADO DA BUSCA SEMÂNTICA (RAG)                    \n"
        "======================================================================\n"
        f"Título:                   {title}\n"
        f"Preço Original:           {currency} {original_price:.2f}\n"
        f"Custo Desembarcado em R$: R$ {custo_desembarcado:.2f}\n"
        f"Pontuação/Relevância:     {relevance_str}\n"
        "======================================================================"
    )


async def run_pipeline(
    search_term: str = DEFAULT_SEARCH_TERM,
    exchange_rate: float = DEFAULT_EXCHANGE_RATE,
    semantic_query: str = DEFAULT_SEMANTIC_QUERY,
    vector_store: Optional[BlurayVectorStore] = None,
    scraper: Optional[EbayScraper] = None,
    max_results: int = 5,
    use_mock_fallback: bool = True,
) -> Optional[Dict[str, Any]]:
    """Executa o pipeline completo: Scraping -> Cálculo Aduaneiro -> Indexação RAG -> Busca Semântica.

    Args:
        search_term: Termo para consulta no eBay.
        exchange_rate: Taxa de câmbio USD/BRL para o cálculo aduaneiro.
        semantic_query: Pergunta ou descrição para a busca vetorial semântica.
        vector_store: Instância do BlurayVectorStore (cria uma nova se None).
        scraper: Instância do EbayScraper (cria uma nova se None).
        max_results: Quantidade máxima de itens a processar.
        use_mock_fallback: Se True, utiliza dados mockados caso a busca ao vivo falhe ou retorne vazio.

    Returns:
        Optional[Dict[str, Any]]: O item mais relevante encontrado pela busca semântica, ou None.
    """
    # 1. Buscar itens no eBay (reais ou mockados)
    items = await fetch_items(
        scraper=scraper,
        search_term=search_term,
        max_results=max_results,
        use_mock_fallback=use_mock_fallback,
    )

    if not items:
        logger.error("Nenhum item foi encontrado para o termo pesquisado.")
        return None

    # 2. Inicializar banco vetorial
    store = vector_store or BlurayVectorStore(collection_name="nolan_bluray_catalog")

    # 3. Processar cada item com cálculo aduaneiro e indexar no vector store
    logger.info("Processando %d itens com cálculo aduaneiro (câmbio = %.2f)...", len(items), exchange_rate)
    for idx, item in enumerate(items, start=1):
        price_usd = float(item.get("price", 0.0))
        shipping_usd = parse_shipping_usd(item.get("shipping", "0.0"))

        duties = calculate_import_duties(
            price_usd=price_usd,
            shipping_usd=shipping_usd,
            exchange_rate=exchange_rate,
        )

        custo_total_brl = duties["custo_total_desembarcado_brl"]
        item_id = f"item-{idx}"
        title = item.get("title", f"Blu-ray Item {idx}")
        currency = item.get("currency", "USD")
        shipping_str = item.get("shipping", "Free shipping")

        document = (
            f"{title}. Preço original: {currency} {price_usd:.2f}. "
            f"Frete: {shipping_str}. Custo total desembarcado: R$ {custo_total_brl:.2f}. "
            f"Imposto federal: R$ {duties['imposto_federal_brl']:.2f}. ICMS: R$ {duties['icms_brl']:.2f}."
        )

        metadata: Dict[str, Any] = {
            "title": title,
            "preco_original": price_usd,
            "moeda_original": currency,
            "shipping": shipping_str,
            "url": item.get("url", ""),
            "custo_base_brl": duties["custo_base_brl"],
            "imposto_federal_brl": duties["imposto_federal_brl"],
            "icms_brl": duties["icms_brl"],
            "custo_total_desembarcado_brl": custo_total_brl,
        }

        store.add_item(
            item_id=item_id,
            title=title,
            preco_brl_desembarcado=custo_total_brl,
            frete=shipping_str,
            moeda_original=currency,
            document=document,
            metadata=metadata,
        )

    logger.info("Total de itens indexados no banco vetorial: %d", store.count())

    # 4. Busca semântica vetorial
    logger.info("Realizando busca semântica por: '%s'...", semantic_query)
    query_results = store.query_similar(query_text=semantic_query, n_results=1)

    if not query_results:
        logger.warning("Nenhum resultado retornado na busca semântica.")
        return None

    top_result = query_results[0]
    formatted_output = format_search_result(top_result)
    print(formatted_output)

    return top_result


def main() -> None:
    """Ponto de entrada síncrono para execução CLI."""
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
