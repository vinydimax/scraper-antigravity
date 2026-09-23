"""Módulo responsável pelo banco vetorial e busca semântica RAG usando ChromaDB."""

import logging
from typing import Any, Dict, List, Optional
import chromadb

logger = logging.getLogger(__name__)


class BlurayVectorStore:
    """Gerenciador de armazenamento vetorial e busca semântica para Blu-rays usando ChromaDB."""

    def __init__(
        self,
        collection_name: str = "bluray_catalog",
        persist_directory: Optional[str] = None,
        client: Optional[Any] = None,
        embedding_function: Optional[Any] = None,
    ) -> None:
        """Inicializa o banco vetorial ChromaDB.

        Args:
            collection_name: Nome da coleção no ChromaDB (padrão: 'bluray_catalog').
            persist_directory: Diretório opcional para persistência em disco. Se None e client for None, opera em memória.
            client: Instância opcional pré-configurada de cliente ChromaDB.
            embedding_function: Função opcional de embedding customizada.

        Raises:
            ValueError: Se collection_name for vazia ou contiver apenas espaços em branco.
        """
        if not collection_name or not collection_name.strip():
            raise ValueError("O nome da coleção (collection_name) não pode ser vazio.")

        self.collection_name = collection_name.strip()

        if client is not None:
            self.client = client
        elif persist_directory:
            self.client = chromadb.PersistentClient(path=persist_directory)
        else:
            self.client = chromadb.EphemeralClient()

        collection_kwargs: dict[str, Any] = {"name": self.collection_name}
        if embedding_function is not None:
            collection_kwargs["embedding_function"] = embedding_function

        self.collection = self.client.get_or_create_collection(**collection_kwargs)

    def add_item(
        self,
        item_id: str,
        title: str,
        preco_brl_desembarcado: float,
        frete: str = "Free shipping",
        moeda_original: str = "USD",
        document: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Indexa um item de Blu-ray no banco vetorial.

        Args:
            item_id: Identificador único do item.
            title: Título do produto ou anúncio de Blu-ray.
            preco_brl_desembarcado: Valor total desembarcado em BRL (com tributos e frete).
            frete: Informação de frete (ex: 'Free shipping', 'US $5.00').
            moeda_original: Moeda de listagem original (ex: 'USD', 'EUR').
            document: Descrição textual completa. Se None, é sintetizada a partir do título e metadados.
            metadata: Metadados estruturados adicionais opcionais.

        Raises:
            ValueError: Se item_id ou title forem vazios, ou se preco_brl_desembarcado < 0.
        """
        if not item_id or not str(item_id).strip():
            raise ValueError("O identificador do item (item_id) não pode ser vazio.")
        if not title or not str(title).strip():
            raise ValueError("O título do item (title) não pode ser vazio.")
        if preco_brl_desembarcado < 0:
            raise ValueError("O preço desembarcado (preco_brl_desembarcado) não pode ser negativo.")

        clean_id = str(item_id).strip()
        clean_title = str(title).strip()
        clean_frete = str(frete).strip() if frete else "Free shipping"
        clean_currency = str(moeda_original).strip() if moeda_original else "USD"

        # Constrói documento descritivo textual se não fornecido
        doc_text = (
            document.strip()
            if document and document.strip()
            else f"{clean_title}. Preço desembarcado: R$ {preco_brl_desembarcado:.2f}. Frete: {clean_frete}. Moeda original: {clean_currency}."
        )

        meta: Dict[str, Any] = {
            "title": clean_title,
            "preco_brl_desembarcado": float(preco_brl_desembarcado),
            "frete": clean_frete,
            "moeda_original": clean_currency,
            "landed_price_brl": float(preco_brl_desembarcado),
            "shipping": clean_frete,
            "original_currency": clean_currency,
        }

        if metadata:
            for key, val in metadata.items():
                if isinstance(val, (str, int, float, bool)):
                    meta[key] = val

        self.collection.upsert(
            ids=[clean_id],
            documents=[doc_text],
            metadatas=[meta],
        )

    def add_items(self, items: List[Dict[str, Any]]) -> None:
        """Indexa múltiplos itens de Blu-ray em lote.

        Args:
            items: Lista de dicionários contendo os dados dos itens a serem indexados.

        Raises:
            ValueError: Se algum item possuir dados inválidos.
        """
        if not items:
            return

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in items:
            raw_id = item.get("id") or item.get("item_id")
            raw_title = item.get("title")
            raw_price = item.get("preco_brl_desembarcado", item.get("landed_price_brl", 0.0))
            raw_frete = item.get("frete", item.get("shipping", "Free shipping"))
            raw_currency = item.get("moeda_original", item.get("original_currency", "USD"))

            if not raw_id or not str(raw_id).strip():
                raise ValueError("Todo item deve possuir um 'id' ou 'item_id' válido.")
            if not raw_title or not str(raw_title).strip():
                raise ValueError("Todo item deve possuir um 'title' válido.")
            if float(raw_price) < 0:
                raise ValueError("O preço desembarcado não pode ser negativo.")

            clean_id = str(raw_id).strip()
            clean_title = str(raw_title).strip()
            preco_val = float(raw_price)
            frete_val = str(raw_frete).strip() if raw_frete else "Free shipping"
            currency_val = str(raw_currency).strip() if raw_currency else "USD"

            doc_text = item.get("document")
            if not doc_text or not str(doc_text).strip():
                doc_text = f"{clean_title}. Preço desembarcado: R$ {preco_val:.2f}. Frete: {frete_val}. Moeda original: {currency_val}."
            else:
                doc_text = str(doc_text).strip()

            meta: Dict[str, Any] = {
                "title": clean_title,
                "preco_brl_desembarcado": preco_val,
                "frete": frete_val,
                "moeda_original": currency_val,
                "landed_price_brl": preco_val,
                "shipping": frete_val,
                "original_currency": currency_val,
            }

            extra = item.get("metadata") or {}
            for k, v in extra.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v

            ids.append(clean_id)
            documents.append(doc_text)
            metadatas.append(meta)

        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def query_similar(self, query_text: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Realiza busca semântica por proximidade vetorial no catálogo indexado.

        Args:
            query_text: Texto ou descrição para a busca semântica.
            n_results: Quantidade máxima de itens a retornar (padrão: 3).

        Returns:
            List[Dict[str, Any]]: Lista de itens ordenados por proximidade vetorial, contendo:
                - id (str): ID do item.
                - document (str): Texto descritivo indexado.
                - metadata (dict): Metadados estruturados.
                - distance (float): Distância vetorial (quanto menor, mais próximo).
                - preco_brl_desembarcado (float): Preço BRL desembarcado.
                - frete (str): Frete.
                - moeda_original (str): Moeda original.
                - title (str): Título do item.

        Raises:
            ValueError: Se query_text for vazio ou n_results <= 0.
        """
        if not query_text or not query_text.strip():
            raise ValueError("O texto de consulta (query_text) não pode ser vazio.")
        if n_results <= 0:
            raise ValueError("O número de resultados (n_results) deve ser maior que zero.")

        total_count = self.collection.count()
        if total_count == 0:
            return []

        # Evita erro do ChromaDB quando n_results é maior que a quantidade total de itens indexados
        actual_n = min(n_results, total_count)
        query_response = self.collection.query(
            query_texts=[query_text.strip()],
            n_results=actual_n,
        )

        results: List[Dict[str, Any]] = []
        ids = query_response.get("ids", [[]])[0]
        documents = query_response.get("documents", [[]])[0] if query_response.get("documents") else []
        metadatas = query_response.get("metadatas", [[]])[0] if query_response.get("metadatas") else []
        distances = query_response.get("distances", [[]])[0] if query_response.get("distances") else []

        for i, item_id in enumerate(ids):
            doc = documents[i] if i < len(documents) else ""
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] is not None else {}
            dist = distances[i] if i < len(distances) else None

            results.append(
                {
                    "id": item_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": dist,
                    "preco_brl_desembarcado": meta.get("preco_brl_desembarcado"),
                    "frete": meta.get("frete"),
                    "moeda_original": meta.get("moeda_original"),
                    "title": meta.get("title"),
                }
            )

        return results

    def count(self) -> int:
        """Retorna o número total de itens indexados na coleção."""
        return self.collection.count()

    def get_item(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Recupera um item específico pelo ID.

        Args:
            item_id: Identificador único do item.

        Returns:
            Optional[Dict[str, Any]]: Dicionário com os dados do item ou None se não encontrado.
        """
        if not item_id or not str(item_id).strip():
            return None

        data = self.collection.get(ids=[str(item_id).strip()])
        ids = data.get("ids", [])
        if not ids:
            return None

        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        doc = documents[0] if documents else ""
        meta = metadatas[0] if metadatas and metadatas[0] is not None else {}

        return {
            "id": ids[0],
            "document": doc,
            "metadata": meta,
            "preco_brl_desembarcado": meta.get("preco_brl_desembarcado"),
            "frete": meta.get("frete"),
            "moeda_original": meta.get("moeda_original"),
            "title": meta.get("title"),
        }

    def delete_item(self, item_id: str) -> None:
        """Remove um item do banco vetorial pelo ID.

        Args:
            item_id: Identificador do item a ser removido.
        """
        if item_id and str(item_id).strip():
            self.collection.delete(ids=[str(item_id).strip()])

