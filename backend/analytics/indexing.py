import os
import requests
from typing import List
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_core.documents import Document
from langchain_text_splitters import TokenTextSplitter
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings
import json
from langchain_experimental.text_splitter import SemanticChunker
from openai import OpenAI
import pandas as pd
import hashlib
import time
import uuid
import tempfile
import shutil
try:
    import boto3
except ImportError:
    boto3 = None
from .models import (
    WebsiteLink,
    KnowledgeBase
)
from backend.settings import logger
from dotenv import load_dotenv
load_dotenv()


def chunk_splitter(
    document: Document,
    embedding_model: str = "text-embedding-3-large",
    chunk_size: int = 1000,
    chunk_overlap: int = 50,
    pdf_local: bool = False,
    semantic: bool = False
) -> List[Document]:
    """
    Splits a document into chunks using OpenAI embeddings and TokenTextSplitter.
    Adjusts chunk size and overlap based on the provided parameters.
    If semantic is True, uses SemanticChunker for chunking.
    Args:
        document (Document): The document to be split.
        embedding_model (str): The OpenAI model to use for embeddings.
        chunk_size (int): The size of each chunk.
        chunk_overlap (int): The overlap between chunks.
        pdf_local (bool): If True, indicates the document is a local PDF.
        semantic (bool): If True, uses SemanticChunker for chunking.
    Returns:
        List[Document]: A list of Document objects representing the chunks.
    """
    logger.info(f"Starting chunk_splitter with chunk_size={chunk_size},")
    logger.info(f"chunk_overlap={chunk_overlap}, pdf_local={pdf_local}, semantic={semantic}")
    embeddings = OpenAIEmbeddings(
        model=embedding_model,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    logger.info("Embeddings created successfully for chunking")
    text_splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    logger.info("Using TokenTextSplitter for splitting")

    if semantic:
        text_splitter = SemanticChunker(
            embeddings,
            breakpoint_threshold_type="percentile"
        )
        logger.info("Using Semantic Chunker for splitting")

    chunks = text_splitter.split_text(document.page_content)
    logger.info("Splitted Document into Chunks")
    if pdf_local:
        new_metadata = {
            "source": document.metadata["source"].split("/")[-1],
            "page": document.metadata.get("page", None),
        }
    else:
        new_metadata = {
            "source": document.metadata["source"],
            "page": document.metadata.get("page", None),
        }
    chunk_documents = []
    for chunk_text in chunks:
        chunk_doc = Document(page_content=chunk_text, metadata=new_metadata)
        chunk_documents.append(chunk_doc)
    logger.info(f"Total Chunks created: {len(chunk_documents)}")
    return chunk_documents


def get_dense_vector(text: str) -> list:
    """
    Dense Vector Embeddings using OpenAI API for vector retrieval.
    Uses the text-embedding-3-large model to generate 1024-dimensional embeddings.
    Args:
        text (str): The input text to generate embeddings for.
    Returns:
        list: A list of 1024-dimensional dense vector embeddings.
    Raises:
        ValueError: If the generated embeddings do not have 1024 dimensions.
        Exception: If there is an error during the OpenAI API call.
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        logger.debug(f"Generating dense vector embeddings for text: {text[:50]}...")
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-large",
            dimensions=1024
        )
        embeddings = response.data[0].embedding
        if len(embeddings) != 1024:
            raise ValueError(f"Expected 1024 dimensions, but got {len(embeddings)}")
        logger.info("Successfully generated dense vector embeddings")
        return embeddings
    except Exception as e:
        logger.error(f"Error in get_dense_vector: {str(e)}")
        raise


def get_sparse_vector(text: str) -> dict:
    """
    Splade Encoder using pinecone-text module for sparse vector retrieval.
    Uses the Sparse Embeddings API to generate sparse vectors.
    Args:
        text (str): The input text to generate sparse embeddings for.
    Returns:
        dict: A dictionary containing 'indices' and 'values' keys representing the sparse vector.
    Raises:
        Exception: If there is an error during the Sparse Embeddings API call.
        ValueError: If the response from the Sparse Embeddings API is not in the expected format.
    """
    url = os.getenv("SPARSE_EMBEDDINGS_API_URL")
    response = requests.post(
        url=url,
        data=json.dumps({"query": text}),
        headers={"Content-type": "application/json"},
    )
    if response.ok:
        doc_sparse_vector = response.json()
        # Ensure the output is a dict with 'indices' and 'values' keys
        if isinstance(doc_sparse_vector, list):
            # Convert list to dict (example: treat as dense, use indices 0..n)
            doc_sparse_vector = {"indices": list(range(len(doc_sparse_vector))), "values": doc_sparse_vector}
        elif isinstance(doc_sparse_vector, dict):
            # If already correct format, just return
            if set(doc_sparse_vector.keys()) >= {"indices", "values"}:
                return doc_sparse_vector
            # If not, try to convert if possible
            elif "values" in doc_sparse_vector and isinstance(doc_sparse_vector["values"], list):
                doc_sparse_vector = {
                    "indices": list(range(len(doc_sparse_vector["values"]))),
                    "values": doc_sparse_vector["values"]
                }
        return doc_sparse_vector
    else:
        logger.error(f"Error in get_sparse_vector {response.text}")
        raise Exception(f"Sparse vector API error: {response.text}")


def encode(text: str, embedding_type: str = "hybrid"):
    """
    Encodes text into dense and sparse vectors based on the specified embedding type.
    Args:
        text (str): The input text to encode.
        embedding_type (str): The type of embedding to use ("dense", "hybrid").
    Returns:
        tuple: A tuple containing dense and sparse vectors.
    Raises:
        Exception: If there is an error during the encoding process.
        ValueError: If the embedding type is not supported.
    """
    try:
        if embedding_type == "dense":
            logger.info("Using Dense Embeddings")
            dense_emb = get_dense_vector(text)
            sparse_emb = {'indices': [0], 'values': [0.1]}
        elif embedding_type == "hybrid":
            dense_emb = get_dense_vector(text)
            sparse_emb = get_sparse_vector(text)
            logger.info("Returning dense_emb and sparse_emb for hybrid embedding type")
        return dense_emb, sparse_emb
    except Exception as e:
        logger.info(f"Error Occured as {e}")
        return [], {'indices': [0], 'values': [0.1]}


def store_chunk_to_pinecone(
    id: str,
    chunk: Document,
    namespace: str,
    index_name: str = os.getenv('PINECONE_INDEX'),
    doc_name: str = 'None',
    doc_link: str = 'None',
    embedding_type: str = "hybrid"
) -> None:
    """
    Stores a chunk of text in Pinecone index with metadata.
    Args:
        id (str): Unique identifier for the chunk.
        chunk (Document): The chunk of text to store.
        namespace (str): The namespace in Pinecone to store the chunk.
        index_name (str): The name of the Pinecone index.
        doc_name (str): The name of the document from which the chunk is derived.
        doc_link (str): The link to the document, if applicable.
        embedding_type (str): The type of embedding to use ("dense", "hybrid").
    Returns:
        None
    Raises:
        Exception: If there is an error during the Pinecone upsert operation.
    """
    logger.info(f"Storing chunk to Pinecone with id={id}, namespace={namespace},")
    logger.info(f"doc_name={doc_name}, doc_link={doc_link}, embedding_type={embedding_type}")
    try:
        logger.debug(f"Chunk metadata: {chunk.metadata}")
        logger.debug(f"Chunk page_content (first 100 chars): {chunk.page_content[:100]}")
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(index_name)
        dense_vec, sparse_vec = encode(chunk.page_content, embedding_type=embedding_type)
        logger.debug(f"Dense vector: {dense_vec[:10]}... (total {len(dense_vec)})")
        logger.debug(f"Sparse vector: {sparse_vec}")
        if len(dense_vec) == 0 and len(sparse_vec) == 0:
            logger.error(f"""
                        Both dense and sparse vectors are empty for chunk id {id}.
                        Chunk content: {chunk.page_content[:200]}
                        """)
            logger.error(f"Chunk metadata: {chunk.metadata}")
            raise Exception("Both dense and sparse vectors are empty")
        metadata = {
            "context": chunk.page_content,
            "doc_name": doc_name,
            "doc_link": doc_link
        }
        logger.debug(f"Metadata to be stored in Pinecone: {metadata}")
        final_packet = {
            "id": id,
            "values": dense_vec,
            "sparse_values": sparse_vec,
            "metadata": metadata,
        }
        logger.debug(f"Final packet for Pinecone upsert: {str(final_packet)[:200]}")
        index.upsert(vectors=[final_packet], namespace=namespace)
        logger.info(f"Index updated with {chunk.metadata['source']} with namespace {namespace}")
    except Exception as e:
        logger.error(f"Error occured in store_chunk_to_pinecone: {e}")


def index_uploaded_documents(
    kb_id,
    knowledge_files_queryset,
    namespace=None,
    chunk_size: int = 1000,
    chunk_overlap: int = 50,
    embedding_type: str = "hybrid"
) -> int:
    """
    Indexes uploaded documents into Pinecone.
    Args:
        kb_id (str): The ID of the knowledge base.
        knowledge_files_queryset (QuerySet): The queryset of knowledge files to index.
        namespace (str): The namespace in Pinecone to store the chunks.
        chunk_size (int): The size of each chunk.
        chunk_overlap (int): The overlap between chunks.
        embedding_type (str): The type of embedding to use ("dense", "hybrid").
    Returns:
        int: The total number of chunks indexed.
    Raises:
        Exception: If there is an error during the indexing process.
    """
    if namespace is None:
        namespace = str(kb_id)
    total_chunks = 0
    logger.info(f"Starting document indexing for assistant {kb_id} with {knowledge_files_queryset.count()} files.")
    for kfile in knowledge_files_queryset:
        s3_url = kfile.file  # S3 URL
        file_ext = os.path.splitext(s3_url)[1].lower()
        doc_name = os.path.basename(s3_url)
        logger.info(f"Processing file: {doc_name} ({file_ext})")
        try:
            if file_ext == ".pdf":
                response = requests.get(s3_url)
                with open("/tmp/tmpfile.pdf", "wb") as tmpf:
                    tmpf.write(response.content)
                pages = PyPDFLoader("/tmp/tmpfile.pdf").load()
                for page in pages:
                    chunks = chunk_splitter(page, chunk_size=chunk_size, chunk_overlap=chunk_overlap, pdf_local=True)
                    logger.info(f"File {doc_name} page {page.metadata.get('page', '?')}: {len(chunks)} semantic chunks")
                    for chunk in chunks:
                        store_chunk_to_pinecone(
                            f"{kfile.id}_{total_chunks}",
                            chunk,
                            namespace=namespace,
                            doc_name=doc_name,
                            embedding_type=embedding_type
                        )
                        total_chunks += 1
            elif file_ext == ".txt":
                response = requests.get(s3_url)
                text = response.text
                doc = Document(page_content=text, metadata={"source": s3_url})
                chunks = chunk_splitter(
                    doc,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                logger.info(f"File {doc_name}: {len(chunks)} semantic chunks")
                for chunk in chunks:
                    store_chunk_to_pinecone(
                        f"{kfile.id}_{total_chunks}",
                        chunk,
                        namespace=namespace,
                        doc_name=doc_name,
                        embedding_type=embedding_type
                    )
                    total_chunks += 1
            elif file_ext == ".docx":
                response = requests.get(s3_url)
                with open("/tmp/tmpfile.docx", "wb") as tmpf:
                    tmpf.write(response.content)
                docs = Docx2txtLoader("/tmp/tmpfile.docx").load()
                for doc in docs:
                    chunks = chunk_splitter(
                        doc,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap
                    )
                    logger.info(f"File {doc_name} docx part: {len(chunks)} semantic chunks")
                    for chunk in chunks:
                        store_chunk_to_pinecone(
                            f"{kfile.id}_{total_chunks}",
                            chunk,
                            namespace=namespace,
                            doc_name=doc_name,
                            embedding_type=embedding_type
                        )
                        total_chunks += 1
            else:
                logger.warning(f"Unsupported file type: {file_ext} for file {doc_name}")

            kfile.indexed = True
            kfile.save()
        except Exception as e:
            logger.error(f"Failed to process {s3_url}: {e}")
            continue
    logger.info(f"Indexed {total_chunks} chunks for assistant {kb_id}")
    return total_chunks


def index_excel_documents(
    kb_id,
    knowledge_excels_queryset,
    namespace=None,
    chunk_size: int = 1000,
    chunk_overlap: int = 50,
    embedding_type: str = "hybrid"
) -> int:
    """
    Indexes Excel/CSV documents into Pinecone.
    Supports .csv, .xlsx, .xls, and similar formats. Handles private S3 buckets using presigned URLs or boto3.
    Uses unique temp filenames and cleans up after processing.
    """
    # Defensive: ensure knowledge_excels_queryset is always iterable
    if not hasattr(knowledge_excels_queryset, '__iter__') or isinstance(knowledge_excels_queryset, (str, bytes)):
        knowledge_excels_queryset = [knowledge_excels_queryset]

    if namespace is None:
        namespace = str(kb_id)
    total_chunks = 0
    logger.info(f"Starting Excel/CSV document indexing for knowledgebase {kb_id} with {knowledge_excels_queryset} files.")
    for kfile in knowledge_excels_queryset:
        s3_url = kfile.file  # S3 URL or path
        file_ext = os.path.splitext(s3_url)[1].lower()
        excel_name = os.path.basename(s3_url)
        logger.info(f"Processing Excel/CSV file: {excel_name} ({file_ext})")
        temp_dir = tempfile.mkdtemp()
        temp_filename = f"{kfile.id}_{uuid.uuid4()}{file_ext}"
        temp_path = os.path.join(temp_dir, temp_filename)
        try:
            # Download file (support presigned URL or boto3 for private S3)
            download_success = False
            if s3_url.startswith("http"):
                try:
                    response = requests.get(s3_url, timeout=60)
                    response.raise_for_status()
                    with open(temp_path, "wb") as tmpf:
                        tmpf.write(response.content)
                    download_success = True
                except Exception as e:
                    logger.warning(f"Failed to download via HTTP: {e}")
            if not download_success and boto3 is not None and s3_url.startswith("s3://"):
                try:
                    s3 = boto3.client("s3")
                    bucket, key = s3_url[5:].split("/", 1)
                    s3.download_file(bucket, key, temp_path)
                    download_success = True
                except Exception as e:
                    logger.error(f"Failed to download from S3 using boto3: {e}")
            if not download_success:
                logger.error(f"Could not download file: {s3_url}")
                continue
            # Read file (support .csv, .xlsx, .xls)
            df = None
            try:
                if file_ext == ".csv":
                    df = pd.read_csv(temp_path)
                elif file_ext in [".xlsx", ".xls"]:
                    df = pd.read_excel(temp_path, engine="openpyxl" if file_ext == ".xlsx" else None)
                else:
                    logger.warning(f"Unsupported file type: {file_ext} for file {excel_name}")
                    continue
            except Exception as e:
                logger.error(f"Failed to read file {temp_path}: {e}")
                continue
            logger.debug(f"df.head(): {df.head()}")
            for index, row in df.iterrows():
                link = str(row[0])
                if link:
                    try:
                        content, hash = scrape_link(link)
                        doc = Document(page_content=content, metadata={"source": getattr(kfile, 'original_name', excel_name)})
                        chunks = chunk_splitter(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                        logger.info(f"Excel/CSV {excel_name} row {index}: {len(chunks)} semantic chunks")
                        for chunk in chunks:
                            store_chunk_to_pinecone(
                                f"{kfile.id}_{total_chunks}",
                                chunk,
                                namespace=namespace,
                                doc_name=excel_name,
                                doc_link=link,
                                embedding_type=embedding_type
                            )
                            total_chunks += 1
                    except Exception as e:
                        logger.warning(f"No content found for link {link} in file {excel_name}: {e}")
                        continue
            kfile.indexed = True
            kfile.save()
        except Exception as e:
            logger.error(f"Failed to process {s3_url}: {e}")
            continue
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as cleanup_err:
                logger.warning(f"Failed to clean up temp files: {cleanup_err}")
    logger.info(f"Indexed {total_chunks} chunks from Excel/CSV files for assistant {kb_id}")
    return total_chunks


def index_scraped_links_with_jina(
    kb_id,
    links_queryset,
    namespace=None,
    chunk_size: int = 1000,
    chunk_overlap: int = 50,
    embedding_type: str = "hybrid"
) -> int:
    """
    Indexes web links using Jina AI for scraping and stores the content in Pinecone.
    Args:
        kb_id (str): The ID of the knowledge base.
        links_queryset (QuerySet): The queryset of website links to index.
        namespace (str): The namespace in Pinecone to store the chunks.
        chunk_size (int): The size of each chunk.
        chunk_overlap (int): The overlap between chunks.
        embedding_type (str): The type of embedding to use ("dense", "hybrid").
    Returns:
        int: The total number of chunks indexed.
    Raises:
        Exception: If there is an error during the indexing process.
    """
    if namespace is None:
        namespace = str(kb_id)
    total_chunks = 0
    logger.debug("Using Jina AI for web scraping. Ensure you have the correct API key set in your environment variables.")
    logger.info(f"Starting link scraping for assistant {kb_id} with {links_queryset} links.")

    for link in links_queryset:
        try:
            logger.info(f"Processing link: {link.url}")
            content, hash = scrape_link(link.url)
            kb = KnowledgeBase.objects.filter(uuid=kb_id).first()
            link_model = WebsiteLink.objects.filter(knowledge_base=kb, url=link).first()
            link_model.hash = hash
            link_model.save()
            doc = Document(page_content=content, metadata={"source": link.url})
            chunks = chunk_splitter(
                doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            logger.info(f"Link {link.url}: {len(chunks)}  chunks")
            logger.debug(f"Link {link.url} content: {chunks}...")
            for chunk in chunks:
                store_chunk_to_pinecone(
                    f"{link.id}_{total_chunks}",
                    chunk,
                    namespace=namespace,
                    doc_link=link.url,
                    embedding_type=embedding_type
                )
                total_chunks += 1

        except Exception as e:
            logger.error(f"Exception indexing {link.url} with Jina AI: {e}")
            continue
        link.indexed = True
        link.save()
    logger.info(f"Indexed {total_chunks} chunks from web links for assistant {kb_id}")
    return


def scrape_link(
    link: str,
    max_retries: int = 3,
    retry_delay: int = 3
) -> tuple:
    """
    Scrape a link using Jina AI, with retry logic on failure.
    Args:
        link (str): The URL to scrape.
        max_retries (int): Maximum number of retries on failure.
        retry_delay (int): Delay in seconds between retries.
    Returns:
        tuple: A tuple containing the scraped content and its hash.
    Raises:
        Exception: If there is an error during the scraping process.
    This function uses Jina AI to scrape the content of a given link.
    It retries up to `max_retries` times if the request fails, with a delay of `retry_delay` seconds between attempts.
    """
    for attempt in range(1, max_retries + 1):
        try:
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {os.getenv('JINA_AI_API_KEY')}",
                "X-Engine": "direct"
            }
            jina_url = f"{os.getenv('JINA_READER_URL')}{link}"
            resp = requests.get(jina_url, headers=headers, timeout=60)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                content = data.get("content", "")
                hash = calculate_hash(content)
                logger.info(f"Content hash for {link}: {hash}")
                return content, hash
            else:
                logger.error(f"Failed to scrape {link} with Jina AI: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Exception scraping {link} with Jina AI (attempt {attempt}): {e}")
        if attempt < max_retries:
            logger.info(f"Retrying scrape_link for {link} in {retry_delay} seconds (attempt {attempt + 1}/{max_retries})...")
            time.sleep(retry_delay)
    raise Exception(f"Failed to scrape {link} after {max_retries} attempts")


def retrieve(
    text: str,
    namespace: str,
    index,
    k=2,
    retrieval_method: str = "hybrid"
) -> dict:
    """
    Retrieve documents from Pinecone index based on the provided text and namespace.
    Args:
        text (str): The input text to retrieve documents for.
        namespace (str): The namespace in Pinecone to query.
        index: The Pinecone index object.
        k (int): The number of top results to return.
        retrieval_method (str): The method of retrieval ("dense", "hybrid").
    Returns:
        dict: The query results from the Pinecone index.
    Raises:
        Exception: If there is an error during the retrieval process.
        ValueError: If the retrieval method is not supported.
    """
    try:
        if retrieval_method == "dense":
            dense, sparse = encode(text, embedding_type="dense")
            result = index.query(
                vector=dense,
                top_k=k,
                include_metadata=True,
                namespace=namespace,
            )
            logger.warning(f"Dense retrieval for text: {text[:50]}... with namespace: {namespace}")
            return result
        elif retrieval_method == "hybrid":
            dense, sparse = encode(text, embedding_type="hybrid")
            result = index.query(
                vector=dense,
                sparse_vector=sparse,
                top_k=k,
                include_metadata=True,
                namespace=namespace,
            )
            logger.warning(f"Hybrid retrieval for text: {text[:50]}... with namespace: {namespace}")
            return result
        else:
            logger.error(f"Unsupported retrieval method: {retrieval_method}")
            return {404: "Unsupported retrieval method"}
    except Exception as e:
        logger.error(f"Error in hybrid-retrieval: {e}")
        return {}


def calculate_hash(link_content: str) -> str:
    """
    Calculate a hash for the link content to detect change.
    Args:
        link_content (str): The content of the link to hash.
    Returns:
        str: The SHA-256 hash of the link content.
    Raises:
        ValueError: If the link content is empty.
    This function uses SHA-256 to generate a hash for the content of a link.
    It is useful for detecting changes in the content over time.
    """
    return hashlib.sha256(link_content.encode('utf-8')).hexdigest()
