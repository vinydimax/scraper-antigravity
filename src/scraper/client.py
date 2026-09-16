"""Módulo cliente para scraping de produtos do eBay."""

import logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
import httpx

from src.scraper.parser import _extract_price_and_currency

logger = logging.getLogger(__name__)

DEFAULT_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.ebay.com/",
}


class EbayScraperError(Exception):
    """Exceção base para erros relacionados ao EbayScraper."""


class EbayScraperTimeoutError(EbayScraperError):
    """Exceção levantada quando ocorre timeout na comunicação com o eBay."""


class EbayScraperHTTPError(EbayScraperError):
    """Exceção levantada quando o eBay retorna um código de status HTTP de erro."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class EbayScraper:
    """Cliente assíncrono para scraping e busca de produtos (Blu-rays) no eBay."""

    BASE_URL: str = "https://www.ebay.com/sch/i.html"

    def __init__(
        self,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 10.0,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        """Inicializa o cliente EbayScraper.

        Args:
            client: Instância opcional de httpx.AsyncClient customizada ou mockada.
            timeout: Tempo limite de espera em segundos (padrão: 10.0s).
            headers: Headers HTTP opcionais para sobrescrever os cabeçalhos padrão.
        """
        self._client: Optional[httpx.AsyncClient] = client
        self.timeout: float = timeout
        self.headers: dict[str, str] = headers.copy() if headers is not None else DEFAULT_HEADERS.copy()
        self._owns_client: bool = client is None

    async def __aenter__(self) -> "EbayScraper":
        """Suporte para gerenciador de contexto assíncrono."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout, headers=self.headers)
            self._owns_client = True
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Encerra a sessão HTTP ao sair do contexto."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search_bluray(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Busca itens de Blu-ray no eBay de forma assíncrona.

        Args:
            query: Termo de pesquisa (ex: 'Oppenheimer', 'Matrix').
            max_results: Quantidade máxima de resultados a retornar (padrão: 5).

        Returns:
            list[dict[str, Any]]: Lista de itens encontrados com title, price, currency, shipping e url.

        Raises:
            ValueError: Se o termo de pesquisa for vazio ou conter apenas espaços em branco.
            EbayScraperTimeoutError: Em caso de timeout na comunicação com o eBay.
            EbayScraperHTTPError: Em caso de status de erro HTTP (ex: 404, 500, 429).
            EbayScraperError: Em caso de erro genérico de rede/conexão.
        """
        if not query or not query.strip():
            raise ValueError("A consulta de busca não pode ser vazia.")

        if max_results <= 0:
            return []

        if self._client is not None:
            return await self._execute_search(self._client, query.strip(), max_results)

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            return await self._execute_search(client, query.strip(), max_results)

    async def _execute_search(
        self,
        client: httpx.AsyncClient,
        clean_query: str,
        max_results: int,
    ) -> list[dict[str, Any]]:
        """Executa a requisição HTTP e trata possíveis exceções de rede."""
        search_term = (
            clean_query
            if "blu-ray" in clean_query.lower() or "bluray" in clean_query.lower()
            else f"{clean_query} blu-ray"
        )
        params = {"_nkw": search_term, "_sacat": "0"}

        try:
            response = await client.get(
                self.BASE_URL,
                params=params,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.error("Timeout na busca por '%s' no eBay: %s", clean_query, exc)
            raise EbayScraperTimeoutError(
                f"Timeout ao consultar o eBay para '{clean_query}': {exc}"
            ) from exc
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.error(
                "Erro HTTP %s na busca por '%s' no eBay: %s",
                status_code,
                clean_query,
                exc,
            )
            raise EbayScraperHTTPError(
                f"Erro HTTP {status_code} retornado pelo eBay: {exc}",
                status_code=status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.error(
                "Erro de rede na busca por '%s' no eBay: %s",
                clean_query,
                exc,
            )
            raise EbayScraperError(
                f"Erro de conexão/rede ao consultar o eBay: {exc}"
            ) from exc

        return self._parse_search_results(response.text, max_results=max_results)

    @staticmethod
    def _parse_search_results(html_content: str, max_results: int) -> list[dict[str, Any]]:
        """Faz o parsing do HTML da página de resultados de busca do eBay."""
        if not html_content or not html_content.strip():
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        item_nodes = soup.select(".s-item")
        if not item_nodes:
            item_nodes = soup.select(".srp-results .s-item, div.s-item__info")

        results: list[dict[str, Any]] = []

        for node in item_nodes:
            if len(results) >= max_results:
                break

            # 1. Título
            title_el = (
                node.select_one(".s-item__title span[role='heading']")
                or node.select_one(".s-item__title")
                or node.select_one("h3.s-item__title")
                or node.select_one("h3")
            )
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            if not title or title.lower() in ("shop on ebay", "results matching fewer words"):
                continue

            # 2. Preço
            price_el = (
                node.select_one(".s-item__price")
                or node.select_one("[data-testid='s-item__price']")
                or node.select_one("span.s-item__price")
            )
            if not price_el:
                continue

            price_raw = price_el.get_text(strip=True)
            try:
                price, currency = _extract_price_and_currency(price_raw)
            except ValueError:
                continue

            # 3. URL do anúncio
            link_el = node.select_one("a.s-item__link") or node.select_one("a[href]")
            url = ""
            if link_el and link_el.get("href"):
                url = str(link_el["href"]).strip()

            # 4. Frete
            shipping_el = (
                node.select_one(".s-item__shipping")
                or node.select_one(".s-item__logisticsCost")
                or node.select_one(".s-item__freeXDays")
            )
            shipping = "Free shipping"
            if shipping_el:
                shipping_text = shipping_el.get_text(separator=" ", strip=True)
                shipping = " ".join(shipping_text.split())

            results.append(
                {
                    "title": title,
                    "price": price,
                    "currency": currency,
                    "shipping": shipping,
                    "url": url,
                }
            )

        return results
