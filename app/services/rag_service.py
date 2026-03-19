import chromadb
from typing import List, Dict, Any
from app.core.schema_definitions import SCHEMA_METADATA

class RAGService:
    def __init__(self):
        # Persistent storage for ChromaDB
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection(name="schema_definitions")
        self._index_schema()

    def _index_schema(self):
        """
        Populate the vector database with schema metadata.
        Each document describes a table and its fields.
        """
        # Force fresh start to ensure latest metadata is used
        try:
            self.client.delete_collection(name="schema_definitions")
        except:
            pass
        self.collection = self.client.get_or_create_collection(name="schema_definitions")

        documents = []
        metadatas = []
        ids = []

        for entry in SCHEMA_METADATA:
            table_name = entry["table"]
            table_desc = entry["description"]
            
            # 1. Index the table itself
            documents.append(f"Table: {table_name}. Description: {table_desc}")
            metadatas.append({"type": "table", "name": table_name})
            ids.append(f"table_{table_name}")

            # 2. Index each field within the table
            for field in entry["fields"]:
                field_name = field["name"]
                field_desc = field["description"]
                documents.append(f"Field: {field_name} in Table: {table_name}. Description: {field_desc}")
                metadatas.append({"type": "field", "table": table_name, "name": field_name})
                ids.append(f"field_{table_name}_{field_name}")

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"RAG indexed {self.collection.count()} schema elements.")

    def retrieve_relevant_context(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Find the most relevant tables and fields for a natural language query.
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        contexts = []
        for i in range(len(results["documents"][0])):
            contexts.append({
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i]
            })
        return contexts

rag_service = RAGService()
