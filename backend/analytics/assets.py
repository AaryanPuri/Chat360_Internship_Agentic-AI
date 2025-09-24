from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .serializers import BoardSerializer

from .tasks import direct_upload_to_s3
from .models import Board
from backend.settings import logger


class S3UploadView(APIView):
    def post(self, request, *args, **kwargs):
        # Check if file is in request
        if "file" not in request.FILES:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES["file"]  # <-- This is InMemoryUploadedFile
        logger.info(f"Received file: {file.name}, size={file.size}, type={file.content_type}")

        # Upload to S3 using your helper
        uploaded_url = direct_upload_to_s3(file)
        logger.info(f" Url created successfully {uploaded_url}")

        if not uploaded_url:
            return Response({"error": "Upload failed"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "url": uploaded_url
        }, status=status.HTTP_201_CREATED)


# ---------- 2. Board CRUD ----------
class BoardViewSet(viewsets.ModelViewSet):
    """CRUD for Boards"""
    serializer_class = BoardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Board.objects.filter(user=self.request.user).order_by('-updated_at')

    def create(self, request):
        name = request.data.get("name")
        description = request.data.get("description", "")
        board = Board.objects.create(
            user=request.user,
            name=name,
            description=description,
            images=[]
        )
        return Response({
            "id": str(board.id),
            "name": board.name,
            "description": board.description,
            "images": board.images
        }, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        board = get_object_or_404(Board, pk=pk, user=request.user)
        board.name = request.data.get("name", board.name)
        board.description = request.data.get("description", board.description)
        board.save()
        return Response({
            "id": str(board.id),
            "name": board.name,
            "description": board.description,
            "images": board.images
        })

    def destroy(self, request, pk=None):
        board = get_object_or_404(Board, pk=pk, user=request.user)
        board.delete()
        return Response({"message": "Board deleted"}, status=status.HTTP_204_NO_CONTENT)


# ---------- 3. Unified Image Management ----------
class BoardImageView(APIView):
    """Unified view for all board image operations"""
    permission_classes = [IsAuthenticated]

    def post(self, request, board_id):
        """Add single or multiple images (uploaded directly to S3)"""
        board = get_object_or_404(Board, pk=board_id, user=request.user)

        files = request.FILES.getlist("images")
        if not files:
            return Response(
                {"error": "'images' files are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        images = board.images or []

        for f in files:
            file_url = direct_upload_to_s3(f)
            if not file_url:
                continue  # skip failed uploads

            images.append({
                "url": file_url,
                "metadata": {
                    "title": request.data.get("title", f.name),
                    "description": request.data.get("description", "")
                }
            })

        board.images = images
        board.save()

        return Response(
            {"message": "Images uploaded successfully", "images": board.images},
            status=status.HTTP_201_CREATED,
        )

    def put(self, request, board_id):
        """Update image by URL or index"""
        board = get_object_or_404(Board, pk=board_id, user=request.user)
        images = board.images or []

        # Update by URL
        if 'old_url' in request.data:
            old_url = request.data.get("old_url")
            new_url = request.data.get("new_url")
            title = request.data.get("title")
            description = request.data.get("description")

            if not old_url:
                return Response({"error": "Missing old_url"}, status=status.HTTP_400_BAD_REQUEST)

            updated = False
            for img in images:
                if img.get("url") == old_url:
                    if new_url:
                        img["url"] = new_url
                    if title is not None:
                        img["metadata"]["title"] = title
                    if description is not None:
                        img["metadata"]["description"] = description
                    updated = True
                    break

            if not updated:
                return Response({"error": "Image not found"}, status=status.HTTP_400_BAD_REQUEST)

        # Update by index
        elif 'image_index' in request.data:
            image_index = request.data.get("image_index")
            if not isinstance(image_index, int) or image_index < 0 or image_index >= len(images):
                return Response({"error": "Invalid image index"}, status=status.HTTP_400_BAD_REQUEST)

            if 'url' in request.data:
                images[image_index]["url"] = request.data.get("url")
            if 'title' in request.data:
                images[image_index]["metadata"]["title"] = request.data.get("title")
            if 'description' in request.data:
                images[image_index]["metadata"]["description"] = request.data.get("description")

        else:
            return Response({"error": "Either 'old_url' or 'image_index' is required"}, status=status.HTTP_400_BAD_REQUEST)

        board.images = images
        board.save()
        return Response({"message": "Image updated", "images": board.images})

    def delete(self, request, board_id):
        """Remove images by URLs or index"""
        board = get_object_or_404(Board, pk=board_id, user=request.user)
        images = board.images or []

        # Remove by URLs
        if 'urls' in request.data:
            urls = request.data.get("urls", [])
            if not isinstance(urls, list) or not urls:
                return Response({"error": "Missing or invalid urls list"}, status=status.HTTP_400_BAD_REQUEST)

            board.images = [img for img in images if img.get("url") not in urls]
            board.save()
            return Response({"message": "Images removed", "images": board.images})
        
        # Remove by index
        elif 'image_index' in request.data:
            image_index = request.data.get("image_index")
            if not isinstance(image_index, int) or image_index < 0 or image_index >= len(images):
                return Response({"error": "Invalid image index"}, status=status.HTTP_400_BAD_REQUEST)

            images.pop(image_index)
            board.images = images
            board.save()
            return Response({"message": "Image removed", "images": board.images})
        else:
            return Response({"error": "Either 'urls' or 'image_index' is required"}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, board_id):
        """List all images in a board"""
        board = get_object_or_404(Board, pk=board_id, user=request.user)
        return Response({"images": board.images or []})
