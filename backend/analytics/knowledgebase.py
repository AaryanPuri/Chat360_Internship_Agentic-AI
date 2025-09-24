from datetime import timedelta
from rest_framework.decorators import (
    api_view,
    permission_classes,
    parser_classes
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import (
    AssistantConfiguration,
    KnowledgeBase,
    KnowledgeFile,
    WebsiteLink
)
from rest_framework.parsers import (
    MultiPartParser,
    JSONParser,
    FormParser
)
import boto3
from botocore.exceptions import NoCredentialsError
import os
from .models import KnowledgeExcel
from pinecone import Pinecone
from pinecone.grpc import PineconeGRPC
from backend.settings import logger
from .models import KnowledgeDataExcel
import pandas as pd
import io

KNOWLEDGEBASE_DIR = os.path.join(os.path.dirname(__file__), 'knowledgebase')
KNOWLEDGEBASE_EXCEL = os.path.join(os.path.dirname(__file__), 'knowledgebase_excel')
os.makedirs(KNOWLEDGEBASE_DIR, exist_ok=True)
os.makedirs(KNOWLEDGEBASE_EXCEL, exist_ok=True)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_knowledge_base(request):
    """Create a new knowledge base for the authenticated user.
    Args:
        request (): _http request object containing the name of the knowledge base in POST data.
    Returns:
        Response: Response object indicating success or failure.
    """
    logger.debug(f"create_knowledge_base HEADERS: {request.headers}")
    if 'Authorization' not in request.headers:
        logger.error("Missing Authorization header in create_knowledge_base")
    name = request.data.get("name")
    if not name:
        return Response({"error": "Name required"}, status=400)
    kb = KnowledgeBase.objects.create(
        user=request.user,
        name=name,
        embedding_type=request.data.get("embedding_type", "dense"),
        chunk_size=request.data.get("chunk_size"),
        chunk_overlap=request.data.get("chunk_overlap"),
    )
    # Always upsert a dummy vector to ensure namespace is created (using PineconeGRPC)
    try:
        pc = PineconeGRPC(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv('PINECONE_INDEX'))
        # Use correct dimension for your index
        index.upsert(
            vectors=[{"id": f"init-{kb.uuid}", "values": [0.1] * 1024, "metadata": {"init": True}}],
            namespace=str(kb.uuid)
        )
        logger.info(f"Pinecone namespace created for KB {kb.uuid}")
    except Exception as e:
        logger.error(f"Error creating Pinecone namespace for KB {kb.uuid}: {e}")

    return Response({"id": kb.id, "name": kb.name, "uuid": str(kb.uuid)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_knowledge_bases(request):
    """
    List all knowledge bases for the authenticated user, including counts of files, links, and dataexcels,
    plus all KB fields.
    """
    bases = KnowledgeBase.objects.filter(user=request.user).order_by('-created_at')
    data = []
    for kb in bases:
        files_count = KnowledgeFile.objects.filter(knowledge_base=kb).count()
        links_count = WebsiteLink.objects.filter(knowledge_base=kb).count()
        excels_count = KnowledgeExcel.objects.filter(knowledge_base=kb).count()
        kb_data = {
            "id": kb.id,
            "uuid": str(kb.uuid),
            "name": kb.name,
            "created_at": kb.created_at,
            "updated_at": kb.updated_at,
            "update_interval": str(kb.update_interval) if kb.update_interval else None,
            "embedding_type": kb.embedding_type,
            "chunk_size": kb.chunk_size,
            "chunk_overlap": kb.chunk_overlap,
            "retrieval_method": kb.retrieval_method,
            "reranking_enabled": kb.reranking_enabled,
            "top_k": kb.top_k,
            "top_k_after_reranking": kb.top_k_after_reranking,
            "sparse_weightage": kb.sparse_weightage,
            "files_count": files_count,
            "links_count": links_count,
            "excels_count": excels_count,
        }
        data.append(kb_data)
    return Response(data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_knowledge_base(request, kb_id):
    """Update an existing knowledge base with new parameters.
    Args:
        request (): _http request object containing the kb_id and parameters to update in POST data.
        kb_id (int): ID of the knowledge base to update.
    Returns:
        Response: Response object indicating success or failure.
    """
    logger.debug(f"update_knowledge_base called with kb_id={kb_id} and user={request.user}")
    name = request.data.get("name")
    reranking_enabled = request.data.get("reranking_enabled")
    top_k = request.data.get("top_k")
    top_k_after_reranking = request.data.get("top_k_after_reranking")
    sparse_weightage = request.data.get("sparse_weightage")
    retrieval_method = request.data.get("retrieval_method")
    embedding_type = request.data.get("embedding_type")
    update_interval = request.data.get("update_interval")
    # check once with fronten

    kb = KnowledgeBase.objects.filter(uuid=kb_id, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)

    if name is not None:
        kb.name = name
    if retrieval_method is not None:
        kb.retrieval_method = retrieval_method
    if embedding_type is not None:
        kb.embedding_type = embedding_type
    if reranking_enabled is not None:
        kb.reranking_enabled = bool(reranking_enabled)
    if top_k is not None:
        try:
            kb.top_k = int(top_k)
        except Exception:
            pass
    if top_k_after_reranking is not None:
        try:
            kb.top_k_after_reranking = int(top_k_after_reranking)
        except Exception:
            pass
    if sparse_weightage is not None:
        try:
            kb.sparse_weightage = float(sparse_weightage)
        except Exception:
            pass
    if update_interval is not None:
        try:
            h, m, s = map(int, update_interval.split(":"))
            kb.update_interval = timedelta(hours=h, minutes=m, seconds=s)
        except Exception:
            pass

    kb.save()

    return Response({
        "id": kb.id,
        "name": kb.name,
        "uuid": str(kb.uuid),
        "embedding_type": kb.embedding_type,
        "chunk_size": kb.chunk_size,
        "chunk_overlap": kb.chunk_overlap,
        "retrieval_method": kb.retrieval_method,
        "reranking_enabled": kb.reranking_enabled,
        "top_k": kb.top_k,
        "top_k_after_reranking": kb.top_k_after_reranking,
        "sparse_weightage": kb.sparse_weightage,
        "update_interval": str(kb.update_interval)
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_knowledge_base(request, kb_id):
    """Delete a knowledge base and its associated Pinecone namespace.
    Args:
        request (): _http request object containing the kb_id in POST data.
        kb_id (int): ID of the knowledge base to delete.
    Returns:
        Response: Response object indicating success or failure.
    """
    logger.debug(f"delete_knowledge_base called with kb_id={kb_id} and user={request.user}")
    kb = KnowledgeBase.objects.filter(uuid=kb_id, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)
    # Delete Pinecone namespace (all vectors)
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv('PINECONE_INDEX'))
        index.delete(delete_all=True, namespace=str(kb.uuid))
    except Exception as e:
        logger.error(f"Error deleting Pinecone namespace for KB {kb.uuid}: {e}")
    kb.delete()
    return Response({"message": "Knowledge base and namespace deleted"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser, FormParser])
def knowledgebase_upload_file(request):
    """
    Upload a file to the knowledge base and store it in S3, segregating by file type.
    """
    kb_uuid = request.query_params.get("kb_uuid")
    logger.debug(f"knowledgebase_upload_file called with kb_uuid={kb_uuid} and user={request.user}")
    file = request.FILES.get("file") or request.data.get("file")
    logger.info(f"File received: {file.name if file else 'None'}")
    if not kb_uuid or not file:
        return Response({"error": "kb_uuid and file required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)

    # Determine file extension and folder
    filename = file.name
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".txt":
        folder = "txt"
    elif ext == ".pdf":
        folder = "pdf"
    elif ext in [".doc", ".docx"]:
        folder = "docs"
    else:
        folder = "others"
    logger.info(f"File extension: {ext}, Folder: {folder}")
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )
    logger.debug(f"s3 client setup {s3}")
    bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
    logger.debug(f"Using S3 bucket: {bucket_name}")
    s3_key = f"agenticAI/media/client_media/{folder}/{kb_uuid}/{filename}"
    logger.debug(f"S3 key: {s3_key}")
    try:
        s3.upload_fileobj(file, bucket_name, s3_key)
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    except NoCredentialsError:
        return Response({"error": "AWS credentials not available."}, status=500)
    except Exception as e:
        return Response({"error": f"S3 upload failed: {str(e)}"}, status=500)

    kf = KnowledgeFile.objects.create(
        knowledge_base=kb,
        file=s3_url,
        original_name=filename,
        doc_name=filename
    )
    return Response({"id": kf.id, "name": kf.original_name, "s3_url": s3_url})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser, FormParser])
def knowledgebase_add_excel(request):
    """
    Upload an Excel file to the knowledge base and store it in S3.
    """
    kb_uuid = request.query_params.get("kb_uuid")
    logger.debug(f"knowledgebase_add_excel called with kb_uuid={kb_uuid} and user={request.user}")
    file = request.FILES.get("file") or request.data.get("file")
    if not kb_uuid or not file:
        return Response({"error": "kb_uuid and file required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )
    bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
    logger.debug(f"Uploading Excel file {file.name} to S3 bucket {bucket_name}")
    s3_key = f"gaadibazaar/agenticAI/media/client_media/excel/{kb_uuid}/{file.name}"
    try:
        s3.upload_fileobj(file, bucket_name, s3_key)
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    except NoCredentialsError:
        return Response({"error": "AWS credentials not available."}, status=500)
    except Exception as e:
        return Response({"error": f"S3 upload failed: {str(e)}"}, status=500)

    kf = KnowledgeExcel.objects.create(
        knowledge_base=kb,
        file=s3_url,
        original_name=file.name,
        excel_name=file.name
    )
    return Response({"id": kf.id, "name": kf.original_name, "s3_url": s3_url})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def knowledgebase_delete_link(request, link_id):
    """Delete a link from the knowledge base.

    Args:
        request (): _http request object containing the kb_uuid in GET parameters.
        link_id (_type_): _id of the link to delete.

    Returns:
        Response: Response object indicating success or failure.
    """
    kb_uuid = request.GET.get("kb_uuid")
    if not kb_uuid:
        return Response({"error": "kb_uuid required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)
    link = WebsiteLink.objects.filter(knowledge_base=kb, id=link_id).first()
    if not link:
        return Response({"error": "Link not found"}, status=404)
    # Delete Pinecone chunks for this link
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(os.getenv('PINECONE_INDEX'))
        # Pinecone query requires a vector, so use a dummy vector and filter
        results = index.query(
            vector=[0.0] * 1024,
            top_k=10000,
            namespace=str(kb_uuid),
            filter={"doc_link": {"$eq": link.url}},
            include_values=False,
            include_metadata=True
        )
        ids_to_delete = [match["id"] for match in results.get("matches", [])]
        if ids_to_delete:
            index.delete(ids=ids_to_delete, namespace=str(kb_uuid))
    except Exception as e:
        logger.error(f"Error deleting Pinecone chunks for link {link.url}: {e}")
    link.delete()
    return Response({"message": "Link deleted"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def knowledgebase_delete_file(request, file_id):
    """
    Delete a file from the knowledge base and remove it from S3.
    """
    from .models import KnowledgeFile
    import boto3

    kf = KnowledgeFile.objects.filter(id=file_id, knowledge_base__user=request.user).first()
    if not kf:
        return Response({"error": "File not found"}, status=404)

    # Remove from S3 if file is a URL
    s3_url = str(kf.file)
    if s3_url.startswith("https://"):
        bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME')
        s3_key = s3_url.split(f"https://{bucket_name}.s3.amazonaws.com/")[-1]
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        )
        try:
            s3.delete_object(Bucket=bucket_name, Key=s3_key)
        except Exception as e:
            return Response({"error": f"S3 delete failed: {str(e)}"}, status=500)

    kf.delete()
    return Response({"success": True})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def knowledgebase_delete_excel(request, kb_uuid):
    """
    Delete an Excel file from the knowledge base and remove it from S3.
    """
    from .models import KnowledgeExcel
    import boto3

    kf = KnowledgeExcel.objects.filter(id=excel_id, knowledge_base__user=request.user).first()
    if not kf:
        return Response({"error": "Excel file not found"}, status=404)

    # Remove from S3 if file is a URL
    s3_url = str(kf.file)
    if s3_url.startswith("https://"):
        bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME', 'knowledgebase_uploaded_file')
        s3_key = s3_url.split(f"https://{bucket_name}.s3.amazonaws.com/")[-1]
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        )
        try:
            s3.delete_object(Bucket=bucket_name, Key=s3_key)
        except Exception as e:
            return Response({"error": f"S3 delete failed: {str(e)}"}, status=500)

    kf.delete()
    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, JSONParser, FormParser])
def knowledge_add_data_excel(request):
    """
    Upload a data Excel or CSV file to the knowledge base and store it in S3.
    Generates a summary (head and info) and saves it in KnowledgeDataExcel.summary.
    """

    kb_uuid = request.query_params.get("kb_uuid")
    file = request.FILES.get("file") or request.data.get("file")
    logger.debug(f"knowledge_add_data_excel called with kb_uuid={kb_uuid} and user={request.user}")
    logger.debug(f"File received: {file.name if file else 'None'}")
    if not kb_uuid or not file:
        return Response({"error": "kb_uuid and file required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)
    
    file_content = file.read() 
    file_bytes = io.BytesIO(file_content)
    file_bytes.seek(0)

    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    )
    bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME', 'knowledgebase_uploaded_file')
    s3_key = f"agenticAI/media/client_media/dataexcel/{kb_uuid}/{file.name}"
    try:
        s3.upload_fileobj(file_bytes, bucket_name, s3_key)
        s3_url = f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"
    except NoCredentialsError:
        return Response({"error": "AWS credentials not available."}, status=500)
    except Exception as e:
        return Response({"error": f"S3 upload failed: {str(e)}"}, status=500)
    
    summary_bytes = io.BytesIO(file_content)
    summary_bytes.seek(0)

    # Generate summary (head and info)
    summary = ""
    try:
        summary_bytes.seek(0)
        ext = os.path.splitext(file.name)[1].lower()
        if ext == ".csv":
            df = pd.read_csv(summary_bytes)
        elif ext in [".xlsx", ".xls", ".xlsm", ".xlsb", ".odf", ".ods", ".odt"]:
            # Use openpyxl for xlsx/xlsm, let pandas auto-detect for others
            engine = 'openpyxl' if ext in [".xlsx", ".xlsm"] else None
            df = pd.read_excel(summary_bytes, engine=engine)
        else:
            raise ValueError("Unsupported file format for summary generation.")
        head = df.head().to_string()
        info_buf = io.StringIO()
        df.info(buf=info_buf)
        info = info_buf.getvalue()
        summary = f"Info:\n{info}\n\nHead:\n{head}"
    except Exception as e:
        summary = f"Could not generate summary: {str(e)}"

    kf = KnowledgeDataExcel.objects.create(
        knowledge_base=kb,
        file=s3_url,
        original_name=file.name,
        data_excel_name=file.name,
        summary=summary
    )
    logger.info("the summary for excel file is {summary}")
    return Response({"id": kf.id, "name": kf.original_name, "s3_url": s3_url, "summary": summary})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_knowledge_data_excel(request):
    """
    Retrieve a specific data Excel file by ID for a knowledge base.
    """
    # data_excel_id = request.data.get("data_excel_id")
    kb_uuid = request.GET.get("kb_uuid") or request.data.get("kb_uuid")
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return None
    files = KnowledgeDataExcel.objects.filter(knowledge_base=kb).order_by("-uploaded_at")
    if not files.exists():
        return Response({"files": []}, status=200)

    return Response({
        "files": [
            {
                "id": f.id,
                "created_at": f.uploaded_at,
                "name": f.original_name,
                "s3_url": str(f.file),
                "summary": f.summary
            }
            for f in files
        ]
    })


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def knowledge_delete_data_excel(request):
    """
    Delete a data Excel file from the knowledge base and remove it from S3.
    """
    from .models import KnowledgeDataExcel
    kb_uuid = request.GET.get("kb_uuid") or request.data.get("kb_uuid")
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return None
    kf = KnowledgeDataExcel.objects.filter(knowledge_base=kb).first()
    if not kf:
        return Response({"error": "Data Excel file not found"}, status=404)

    s3_url = str(kf.file)
    if s3_url.startswith("https://"):
        bucket_name = os.getenv('AWS_STORAGE_BUCKET_NAME', 'knowledgebase_uploaded_file')
        s3_key = s3_url.split(f"https://{bucket_name}.s3.amazonaws.com/")[-1]
        s3 = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        )
        try:
            s3.delete_object(Bucket=bucket_name, Key=s3_key)
        except Exception as e:
            return Response({"error": f"S3 delete failed: {str(e)}"}, status=500)

    kf.delete()
    return Response({"success": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def knowledgebase_add_link(request):
    """Add a link to the knowledge base.
    Args:
        request (): _http request object containing kb_uuid, url, title, and grabber_enabled in POST data.
    Returns:
        Response: Response object indicating success or failure.
    """
    logger.debug(f"knowledgebase_add_link called with data: {request.data}")
    kb_uuid = request.data.get("kb_uuid")
    url = request.data.get("url")
    title = request.data.get("title")
    grabber_enabled = request.data.get("grabber_enabled", False)
    grabbed = request.data.get("grabbed", False)
    update_dynamically = request.data.get("update_dynamically", False)
    hash = request.data.get("hash", False)
    indexed = request.data.get("indexed", False)
    logger.debug(f"grabber_enabled: {grabber_enabled}")
    logger.debug(f"update_dynamically: {update_dynamically}")
    if not kb_uuid or not url:
        logger.error(f"Missing kb_uuid or url: kb_uuid={kb_uuid}, url={url}")
        return Response({"error": "kb_uuid and url required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        logger.error(f"Knowledge base not found for uuid={kb_uuid}")
        return Response({"error": "Knowledge base not found"}, status=404)
    link = WebsiteLink.objects.create(knowledge_base=kb, url=url, title=title, grabber_enabled=grabber_enabled, update_dynamically=update_dynamically, grabbed=grabbed, hash=hash, indexed=indexed)
    logger.info(f"Link added: {url} to KB {kb_uuid} (grabber_enabled={grabber_enabled})")
    return Response(
        {
            "id": link.id,
            "url": link.url,
            "title": link.title,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
            "grabber_enabled": link.grabber_enabled,
            "update_dynamically": link.update_dynamically,
            "grabbed": link.grabbed,
            "hash": link.hash,
            "indexed": link.indexed
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledgebase_list_links(request):
    """List all links for a knowledge base.

    Args:
        request (): _http request object containing the kb_uuid in GET parameters.

    Returns:
        Response: Response object containing the list of links or an error message.
    """
    logger.debug(f"knowledgebase_list_links called with params: {request.GET}")
    kb_uuid = request.GET.get("kb_uuid") or request.data.get("kb_uuid")
    if not kb_uuid:
        logger.error("kb_uuid required for listing links")
        return Response({"error": "kb_uuid required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        logger.error(f"Knowledge base not found for uuid={kb_uuid}")
        return Response({"error": "Knowledge base not found"}, status=404)
    links = WebsiteLink.objects.filter(knowledge_base=kb)
    logger.info(f"Listing {links.count()} links for KB {kb_uuid}")
    return Response({"links": [
        {
            "id": link.id,
            "url": link.url,
            "title": link.title,
            "created_at": link.created_at,
            "updated_at": link.updated_at,
            "grabber_enabled": link.grabber_enabled,
            "update_dynamically": link.update_dynamically,
            "grabbed": link.grabbed,
            "hash": link.hash,
            "indexed": link.indexed
        }
        for link in links
    ]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledgebase_list_files(request):
    """List all files for a knowledge base.
    Args:
        request (): _http request object containing the kb_uuid in GET parameters.
    Returns:
        Response: Response object containing the list of files or an error message.
    """
    logger.debug(f"knowledgebase_list_files GET: {request.GET}, DATA: {request.data}")
    kb_uuid = request.GET.get("kb_uuid") or request.data.get("kb_uuid")
    if not kb_uuid:
        logger.error(f"Missing kb_uuid: kb_uuid={kb_uuid}")
        return Response({"error": "kb_uuid required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        logger.error(f"Knowledge base not found for uuid={kb_uuid}")
        return Response({"error": "Knowledge base not found"}, status=404)
    files = KnowledgeFile.objects.filter(knowledge_base=kb)
    logger.info(f"Listing files for KB {kb_uuid}: {[f.original_name for f in files]}")
    return Response({"files": [{"id": f.id, "name": f.original_name} for f in files]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def knowledgebase_list_excels(request):
    """List all Excel files for a knowledge base.
    Args:
        request (): _http request object containing the kb_uuid in GET parameters.
    Returns:
        Response: Response object containing the list of Excel files or an error message.
    """
    logger.debug(f"knowledgebase_list_excel GET: {request.GET}, DATA: {request.data}")
    kb_uuid = request.GET.get("kb_uuid") or request.data.get("kb_uuid")
    if not kb_uuid:
        logger.error(f"Missing kb_uuid: kb_uuid={kb_uuid}")
        return Response({"error": "kb_uuid required"}, status=400)
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not kb:
        return Response({"error": "Knowledge base not found"}, status=404)
    files = KnowledgeExcel.objects.filter(knowledge_base=kb)
    logger.info(f"Listing Excel files for KB {kb_uuid}: {[f.original_name for f in files]}")
    return Response({"files": [{"id": f.id, "name": f.original_name} for f in files]})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def set_assistant_kb(request):
    """Set the knowledge base for an assistant configuration.
    Args:
        request (): _http request object containing model_uuid and knowledge_base in POST data.
    Returns:
        Response: Response object indicating success or failure.
    """
    model_uuid = request.data.get("model_uuid")
    kb_uuid = request.data.get("knowledge_base")
    if not kb_uuid:
        logger.info("knowledge_base is not provided")
        return Response({"success": True, "knowledge_base": None}, status=200)
    logger.info(f"set_assistant_kb DATA: {request.data}")
    if not model_uuid:
        return Response({"error": "model_uuid required"}, status=400)
    config = AssistantConfiguration.objects.filter(user=request.user, assistant_uuid=model_uuid).first()
    kb = KnowledgeBase.objects.filter(uuid=kb_uuid, user=request.user).first()
    if not config or not kb:
        return Response({"error": "Config or KnowledgeBase not found"}, status=404)
    config.knowledge_base = kb
    config.save()
    return Response({"success": True, "knowledge_base": str(kb.uuid)})
