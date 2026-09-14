"""Módulo responsável pelo parsing e extração de dados de produtos do eBay."""

import re
from typing import Any, Dict, Optional, Tuple
from bs4 import BeautifulSoup

CURRENCY_MAP: dict[str, str] = {
    "$": "USD",
    "US $": "USD",
    "USD": "USD",
    "EUR": "EUR",
    "€": "EUR",
    "GBP": "GBP",
    "£": "GBP",
    "R$": "BRL",
    "BRL": "BRL",
    "CAD": "CAD",
    "C $": "CAD",
    "AUD": "AUD",
    "AU $": "AUD",
}


def _extract_price_and_currency(price_raw: str) -> Tuple[float, str]:
    """Extrai o valor numérico (float) e a moeda de uma string de preço."""
    clean_raw = price_raw.strip()

    # Identifica código da moeda pelo símbolo ou texto
    currency = "USD"
    for symbol, code in sorted(CURRENCY_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if symbol in clean_raw:
            currency = code
            break

    # Extrai o valor numérico considerando formatos comuns (ex: 24.99, 1,299.99 ou 24,99)
    match = re.search(r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})|\d+(?:[.,]\d{1,2})?)", clean_raw)
    if not match:
        raise ValueError(f"Não foi possível extrair o valor numérico do preço: '{price_raw}'")

    num_str = match.group(1)
    if "," in num_str and "." in num_str:
        if num_str.find(",") < num_str.find("."):
            num_str = num_str.replace(",", "")
        else:
            num_str = num_str.replace(".", "").replace(",", ".")
    elif "," in num_str:
        num_str = num_str.replace(",", ".")

    return float(num_str), currency


def parse_ebay_item(html_content: str) -> Dict[str, Any]:
    """Extrai título, preço, moeda e frete de uma página HTML de item do eBay.

    Args:
        html_content: String contendo o HTML da página do produto.

    Returns:
        Dict[str, Any] contendo:
            - title (str): Título do item.
            - price (float): Valor numérico do produto.
            - currency (str): Código da moeda (ex: 'USD', 'EUR', 'BRL').
            - shipping (str): Informações de frete (ex: 'Free shipping', 'US $4.99').

    Raises:
        ValueError: Se o HTML for vazio ou se título/preço não forem encontrados.
    """
    if not html_content or not html_content.strip():
        raise ValueError("O conteúdo HTML fornecido está vazio.")

    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Extração do Título
    title: Optional[str] = None
    title_el = (
        soup.select_one("h1.x-item-title__mainTitle span.ux-textspans")
        or soup.select_one("h1.x-item-title__mainTitle")
        or soup.select_one("h1#itemTitle")
        or soup.select_one("[data-testid='x-item-title']")
        or soup.select_one("h1")
    )

    if title_el:
        title = title_el.get_text(strip=True)
        title = re.sub(r"^Details about\s+", "", title, flags=re.IGNORECASE)

    if not title:
        meta_title = soup.find("meta", property="og:title")
        if meta_title and meta_title.get("content"):
            title = str(meta_title["content"]).strip()

    if not title:
        raise ValueError("Título do item não encontrado no HTML fornecido.")

    # 2. Extração do Preço
    price_el = (
        soup.select_one("div.x-price-primary span.ux-textspans")
        or soup.select_one("div.x-price-primary")
        or soup.select_one("[data-testid='x-price-primary']")
        or soup.select_one("span#prcIsum")
        or soup.select_one("span[itemprop='price']")
    )

    if not price_el:
        raise ValueError("Preço do item não encontrado no HTML fornecido.")

    price_raw = price_el.get_text(strip=True)
    price, currency = _extract_price_and_currency(price_raw)

    # 3. Extração do Frete
    shipping_el = (
        soup.select_one("div.ux-labels-values--shipping span.ux-textspans")
        or soup.select_one("div.ux-labels-values--shipping")
        or soup.select_one("[data-testid='x-shipping-cost']")
        or soup.select_one("span#fshippingCost")
        or soup.select_one("div.ux-labels-values__values-content--shipping")
    )

    shipping = "Free shipping"
    if shipping_el:
        shipping_text = shipping_el.get_text(separator=" ", strip=True)
        shipping = " ".join(shipping_text.split())

    return {
        "title": title,
        "price": price,
        "currency": currency,
        "shipping": shipping,
    }
