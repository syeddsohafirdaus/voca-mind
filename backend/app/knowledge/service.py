import hashlib
from typing import List
from app.knowledge.schemas import ChunkMetadata, KnowledgeChunk, KnowledgeDocument


def validate_knowledge_document(doc: KnowledgeDocument) -> bool:
    """Validates that a KnowledgeDocument meets all structural and safety criteria.

    Raises ValueError if invalid, otherwise returns True.
    """
    if not doc.content or not doc.content.strip():
        raise ValueError("Document content cannot be empty or blank.")
    if not doc.title or not doc.title.strip():
        raise ValueError("Document title cannot be empty or blank.")
    if not doc.source_name or not doc.source_name.strip():
        raise ValueError("Document source_name cannot be empty or blank.")
    if not doc.topic or not doc.topic.strip():
        raise ValueError("Document topic cannot be empty or blank.")
    return True


def chunk_document(
    doc: KnowledgeDocument,
    max_chunk_size: int = 500,
    overlap: int = 50,
) -> List[KnowledgeChunk]:
    """Splits a KnowledgeDocument into deterministic chunks preserving source provenance.

    Parameters:
    - doc: The input KnowledgeDocument.
    - max_chunk_size: Maximum character length per chunk (must be > 0).
    - overlap: Overlap character length between sequential chunks (must be >= 0 and < max_chunk_size).

    Returns a list of KnowledgeChunk objects with deterministic chunk IDs and ordering.
    Raises ValueError if doc content is empty/blank or parameters are invalid.
    """
    validate_knowledge_document(doc)

    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be greater than 0.")
    if overlap < 0 or overlap >= max_chunk_size:
        raise ValueError("overlap must be non-negative and strictly less than max_chunk_size.")

    content = doc.content.strip()
    content_len = len(content)
    step = max_chunk_size - overlap

    # Calculate slices
    slices = []
    start = 0
    while start < content_len:
        end = min(start + max_chunk_size, content_len)
        slices.append((start, end))
        if end >= content_len:
            break
        start += step

    total_chunks = len(slices)
    chunks: List[KnowledgeChunk] = []

    for index, (start_char, end_char) in enumerate(slices):
        chunk_text = content[start_char:end_char]
        
        # Deterministic chunk ID using parent document_id and zero-based index
        chunk_id = f"{doc.document_id}_c{index:03d}"

        chunk_metadata = ChunkMetadata(
            source_type=doc.source_type,
            publisher=doc.publisher,
            version=doc.version,
            reviewed=doc.reviewed,
            publication_date=doc.publication_date,
            last_reviewed_date=doc.last_reviewed_date,
            total_chunks=total_chunks,
            start_char=start_char,
            end_char=end_char,
        )

        chunk = KnowledgeChunk(
            chunk_id=chunk_id,
            document_id=doc.document_id,
            chunk_index=index,
            text=chunk_text,
            title=doc.title,
            source_name=doc.source_name,
            source_url=doc.source_url,
            topic=doc.topic,
            language=doc.language,
            metadata=chunk_metadata,
        )
        chunks.append(chunk)

    return chunks
