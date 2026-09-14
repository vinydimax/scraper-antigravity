"""Testes unitários para o módulo parser."""

import pytest
from src.scraper.parser import parse_ebay_item


MOCK_BLURAY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Oppenheimer 4K UHD Blu-ray | eBay</title>
</head>
<body>
    <div class="vim x-item-title">
        <h1 class="x-item-title__mainTitle">
            <span class="ux-textspans">Oppenheimer [New 4K Ultra HD Blu-ray] With Slipcover, Widescreen</span>
        </h1>
    </div>
    <div class="x-price-primary">
        <span class="ux-textspans">US $27.99</span>
    </div>
    <div class="ux-labels-values--shipping">
        <span class="ux-textspans">Free shipping</span>
    </div>
</body>
</html>
"""

MOCK_BLURAY_WITH_SHIPPING_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dune: Part Two Blu-ray | eBay</title>
</head>
<body>
    <div class="vim x-item-title">
        <h1 class="x-item-title__mainTitle">
            <span class="ux-textspans">Dune: Part Two (Blu-ray + Digital) Limited Edition</span>
        </h1>
    </div>
    <div class="x-price-primary">
        <span class="ux-textspans">US $34.50</span>
    </div>
    <div class="ux-labels-values--shipping">
        <span class="ux-textspans">US $4.99 Standard Shipping</span>
    </div>
</body>
</html>
"""

MOCK_BLURAY_EUR_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>The Dark Knight Trilogy Blu-ray | eBay</title>
</head>
<body>
    <div class="vim x-item-title">
        <h1 class="x-item-title__mainTitle">
            <span class="ux-textspans">The Dark Knight Trilogy [Blu-ray] [2005] [Region Free]</span>
        </h1>
    </div>
    <div class="x-price-primary">
        <span class="ux-textspans">EUR 19.95</span>
    </div>
    <div class="ux-labels-values--shipping">
        <span class="ux-textspans">EUR 3.50 International Shipping</span>
    </div>
</body>
</html>
"""


def test_parse_ebay_item_bluray_free_shipping():
    """Valida extração correta de dados de produto Blu-ray com frete grátis."""
    result = parse_ebay_item(MOCK_BLURAY_HTML)

    assert result["title"] == "Oppenheimer [New 4K Ultra HD Blu-ray] With Slipcover, Widescreen"
    assert isinstance(result["price"], float)
    assert result["price"] == 27.99
    assert result["currency"] == "USD"
    assert result["shipping"] == "Free shipping"


def test_parse_ebay_item_bluray_with_shipping_fee():
    """Valida extração correta de produto Blu-ray com taxa de frete."""
    result = parse_ebay_item(MOCK_BLURAY_WITH_SHIPPING_HTML)

    assert result["title"] == "Dune: Part Two (Blu-ray + Digital) Limited Edition"
    assert isinstance(result["price"], float)
    assert result["price"] == 34.50
    assert result["currency"] == "USD"
    assert result["shipping"] == "US $4.99 Standard Shipping"


def test_parse_ebay_item_different_currency():
    """Valida extração correta de preço em EUR."""
    result = parse_ebay_item(MOCK_BLURAY_EUR_HTML)

    assert result["title"] == "The Dark Knight Trilogy [Blu-ray] [2005] [Region Free]"
    assert result["price"] == 19.95
    assert result["currency"] == "EUR"
    assert result["shipping"] == "EUR 3.50 International Shipping"


def test_parse_ebay_item_empty_html():
    """Valida que HTML vazio levanta ValueError."""
    with pytest.raises(ValueError, match="conteúdo HTML fornecido está vazio"):
        parse_ebay_item("")


def test_parse_ebay_item_missing_price():
    """Valida erro quando preço não está presente na página."""
    html_without_price = "<h1>Title</h1>"
    with pytest.raises(ValueError, match="Preço do item não encontrado"):
        parse_ebay_item(html_without_price)


def test_parse_ebay_item_missing_title():
    """Valida erro quando título não está presente na página."""
    html_without_title = "<div class='x-price-primary'>US $10.00</div>"
    with pytest.raises(ValueError, match="Título do item não encontrado"):
        parse_ebay_item(html_without_title)
