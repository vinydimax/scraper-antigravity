"""Testes unitários para o banco vetorial e camada RAG (BlurayVectorStore)."""

import uuid
import chromadb
import pytest
from src.rag.vector_store import BlurayVectorStore


@pytest.fixture
def memory_store() -> BlurayVectorStore:
    """Fixture que fornece um BlurayVectorStore em memória isolado."""
    client = chromadb.EphemeralClient()
    col_name = f"test_store_{uuid.uuid4().hex[:8]}"
    return BlurayVectorStore(collection_name=col_name, client=client)


def test_init_ephemeral(memory_store: BlurayVectorStore) -> None:
    """Valida a inicialização da coleção em memória."""
    assert memory_store.count() == 0
    assert memory_store.collection_name.startswith("test_store_")


def test_init_invalid_collection_name() -> None:
    """Valida erro ao fornecer nome de coleção vazio."""
    with pytest.raises(ValueError) as exc_info:
        BlurayVectorStore(collection_name="   ")
    assert "collection_name" in str(exc_info.value)


def test_add_single_item(memory_store: BlurayVectorStore) -> None:
    """Valida a inserção e recuperação de um único item de Blu-ray."""
    memory_store.add_item(
        item_id="bluray-001",
        title="Oppenheimer 4K UHD Blu-ray",
        preco_brl_desembarcado=289.16,
        frete="Free shipping",
        moeda_original="USD",
    )

    assert memory_store.count() == 1

    item = memory_store.get_item("bluray-001")
    assert item is not None
    assert item["id"] == "bluray-001"
    assert "Oppenheimer" in item["document"]
    assert item["preco_brl_desembarcado"] == 289.16
    assert item["frete"] == "Free shipping"
    assert item["moeda_original"] == "USD"
    assert item["metadata"]["title"] == "Oppenheimer 4K UHD Blu-ray"


def test_add_items_batch(memory_store: BlurayVectorStore) -> None:
    """Valida a indexação de múltiplos itens em lote."""
    items = [
        {
            "id": "item-101",
            "title": "Matrix Revolutions 4K Blu-ray",
            "preco_brl_desembarcado": 190.50,
            "frete": "US $4.00",
            "moeda_original": "USD",
        },
        {
            "id": "item-102",
            "title": "Inception Steelbook Blu-ray",
            "preco_brl_desembarcado": 220.00,
            "frete": "Free shipping",
            "moeda_original": "USD",
        },
    ]

    memory_store.add_items(items)
    assert memory_store.count() == 2

    item_101 = memory_store.get_item("item-101")
    assert item_101 is not None
    assert item_101["preco_brl_desembarcado"] == 190.50
    assert item_101["frete"] == "US $4.00"


def test_semantic_query_similar(memory_store: BlurayVectorStore) -> None:
    """Valida a busca semântica por proximidade vetorial."""
    catalog = [
        {
            "id": "nolan-space",
            "title": "Interstellar Sci-Fi Space Exploration Matthew McConaughey 4K Blu-ray",
            "preco_brl_desembarcado": 245.00,
            "frete": "Free shipping",
            "moeda_original": "USD",
        },
        {
            "id": "spiderman-anim",
            "title": "Spider-Man Into The Spider-Verse Animated Superhero Miles Morales Blu-ray",
            "preco_brl_desembarcado": 150.00,
            "frete": "Free shipping",
            "moeda_original": "USD",
        },
        {
            "id": "nolan-atomic",
            "title": "Oppenheimer Christopher Nolan Atomic Manhattan Project 4K Blu-ray",
            "preco_brl_desembarcado": 289.16,
            "frete": "Free shipping",
            "moeda_original": "USD",
        },
    ]
    memory_store.add_items(catalog)

    # 1. Consulta semântica sobre astronauta e espaço
    space_results = memory_store.query_similar("astronaut wormhole black hole space voyage", n_results=1)
    assert len(space_results) == 1
    assert space_results[0]["id"] == "nolan-space"
    assert space_results[0]["preco_brl_desembarcado"] == 245.00
    assert space_results[0]["distance"] is not None

    # 2. Consulta semântica sobre animação de super-herói
    hero_results = memory_store.query_similar("comic book hero cartoon animation", n_results=2)
    assert len(hero_results) == 2
    assert hero_results[0]["id"] == "spiderman-anim"
    assert hero_results[0]["preco_brl_desembarcado"] == 150.00


def test_query_empty_collection(memory_store: BlurayVectorStore) -> None:
    """Valida que uma consulta em coleção vazia retorna lista vazia."""
    results = memory_store.query_similar("qualquer busca")
    assert results == []


def test_query_n_results_greater_than_collection_size(memory_store: BlurayVectorStore) -> None:
    """Valida que solicitar mais resultados que o tamanho da base não quebra."""
    memory_store.add_item(
        item_id="solo-01",
        title="Dune Part Two 4K Blu-ray",
        preco_brl_desembarcado=299.90,
    )

    results = memory_store.query_similar("arrakis desert spice", n_results=10)
    assert len(results) == 1
    assert results[0]["id"] == "solo-01"


def test_delete_item(memory_store: BlurayVectorStore) -> None:
    """Valida a exclusão de itens da coleção."""
    memory_store.add_item(
        item_id="del-01",
        title="Avatar The Way of Water Blu-ray",
        preco_brl_desembarcado=180.00,
    )
    assert memory_store.count() == 1

    memory_store.delete_item("del-01")
    assert memory_store.count() == 0
    assert memory_store.get_item("del-01") is None


def test_persistent_directory(tmp_path: pytest.TempPathFactory) -> None:
    """Valida a criação e persistência em disco local."""
    persist_dir = str(tmp_path / "chroma_db_test")
    store = BlurayVectorStore(collection_name="disk_catalog", persist_directory=persist_dir)
    store.add_item(
        item_id="disk-01",
        title="The Dark Knight 4K Blu-ray",
        preco_brl_desembarcado=210.00,
    )
    assert store.count() == 1

    # Reabre a coleção a partir do mesmo diretório
    reopened_store = BlurayVectorStore(collection_name="disk_catalog", persist_directory=persist_dir)
    assert reopened_store.count() == 1
    assert reopened_store.get_item("disk-01") is not None


@pytest.mark.parametrize(
    "item_id,title,price,err_substr",
    [
        ("", "Titulo Valido", 100.0, "item_id"),
        ("id-1", "", 100.0, "title"),
        ("id-2", "Titulo", -10.0, "preco_brl_desembarcado"),
    ],
)
def test_add_item_invalid_inputs(
    memory_store: BlurayVectorStore, item_id: str, title: str, price: float, err_substr: str
) -> None:
    """Valida tratamento de erros em add_item."""
    with pytest.raises(ValueError) as exc_info:
        memory_store.add_item(item_id=item_id, title=title, preco_brl_desembarcado=price)
    assert err_substr in str(exc_info.value)


@pytest.mark.parametrize(
    "query_text,n_results,err_substr",
    [
        ("", 3, "query_text"),
        ("   ", 3, "query_text"),
        ("valido", 0, "n_results"),
        ("valido", -1, "n_results"),
    ],
)
def test_query_similar_invalid_inputs(
    memory_store: BlurayVectorStore, query_text: str, n_results: int, err_substr: str
) -> None:
    """Valida tratamento de erros em query_similar."""
    with pytest.raises(ValueError) as exc_info:
        memory_store.query_similar(query_text=query_text, n_results=n_results)
    assert err_substr in str(exc_info.value)


def test_add_items_batch_invalid_inputs(memory_store: BlurayVectorStore) -> None:
    """Valida tratamento de erro ao indexar lote com item inválido."""
    invalid_batch = [
        {"id": "valid-1", "title": "Titulo Valido", "preco_brl_desembarcado": 100.0},
        {"id": "", "title": "Item Sem Id", "preco_brl_desembarcado": 50.0},
    ]
    with pytest.raises(ValueError) as exc_info:
        memory_store.add_items(invalid_batch)
    assert "item_id" in str(exc_info.value) or "id" in str(exc_info.value)
