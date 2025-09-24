from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import uuid
from django.utils.translation import gettext_lazy as _
from django.db.models import JSONField


class CustomUser(AbstractUser):
    phone_number = models.CharField(max_length=32, blank=True, null=True)
    role = models.CharField(max_length=64, blank=True, null=True)
    api_key = models.CharField(max_length=128, blank=True, null=True)
    utc_offset = models.CharField(max_length=16, blank=True, null=True)
    avatar = models.URLField(max_length=500, blank=True, null=True)


class UserData(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    data = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Data for {self.user.username} at {self.created_at}"


class AssistantConfiguration(models.Model):
    assistant_uuid = models.UUIDField(
        _("Assistant UUID"),
        default=uuid.uuid4,
        editable=False,
        null=False
    )
    archived_at = models.DateTimeField(null=True, blank=True, help_text="When the assistant was archived.")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    assistant_name = models.CharField(max_length=100, default="SupportGPT")
    agent_name = models.CharField(max_length=100, default="Agent360", null=True, blank=True)
    organisation_name = models.CharField(max_length=100, null=True, blank=True)
    organisation_description = models.TextField(null=True, blank=True)
    examples = JSONField(null=True, blank=True)
    goal = models.TextField(null=True, blank=True)
    use_last_user_language = models.BooleanField(default=True)
    languages = models.TextField(null=True, blank=True)
    conversation_tone = models.CharField(max_length=50, default="Friendly & Approachable")
    system_instructions = models.TextField(blank=True)
    model_provider = models.CharField(max_length=50, default="OpenAI")
    model_name = models.CharField(max_length=50, default="gpt-4.1-nano")
    temperature = models.FloatField(default=0.7)
    max_tokens = models.IntegerField(default=1024)
    top_p = models.FloatField(default=0.95)
    frequency_penalty = models.FloatField(default=0)
    stream_responses = models.BooleanField(default=False)
    json_mode = models.BooleanField(default=False)
    data_to_capture = models.JSONField(default=list, blank=True, null=True, help_text="Data to capture from user interactions")
    # Tool configuration
    auto_tool_choice = models.BooleanField(default=False)
    selected_tools = models.JSONField(default=list, blank=True, null=True, help_text="List of selected tool names")
    integration_tools = models.JSONField(default=list, blank=True, null=True, help_text="List of integration tool ids")
    selected_boards = models.JSONField(default=list, blank=True, null=True, help_text="List of selected boards")

    # Capabilities
    product_info = models.BooleanField(default=False)
    order_management = models.BooleanField(default=False)
    customer_db = models.BooleanField(default=False)
    payment_processing = models.BooleanField(default=False)
    appointment_booking = models.BooleanField(default=False)
    faqs_kb = models.BooleanField(default=False)

    # Knowledge processing instructions
    knowledge_processing_instructions = models.TextField(blank=True)

    # Link to KnowledgeBase (nullable)
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assistant_configurations'
    )

    enable_emojis = models.BooleanField(default=False)
    answer_competitor_queries = models.BooleanField(default=False)
    competitor_response_bias = models.CharField(
        max_length=16,
        choices=[('genuine', 'Genuine'), ('biased', 'Biased')],
        default='genuine'
    )
    # Timestamp
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete flag

    def __str__(self):
        return self.assistant_name


class WebsiteLink(models.Model):
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.CASCADE,
        related_name="website_links",
        blank=True,
        null=True
    )
    url = models.URLField(max_length=500)
    title = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    grabber_enabled = models.BooleanField(default=False)  # Flag to indicate if link grabbing is enabled
    grabbed = models.BooleanField(default=False)  # Indicates if this link was added via a link grabber
    update_dynamically = models.BooleanField(default=False)  # Flag to indicate if the link should be updated dynamically
    hash = models.CharField(max_length=64, blank=True, null=True)  # Unique hash for the URL
    indexed = models.BooleanField(default=False)  # Flag to indicate if the link has been indexed

    def __str__(self):
        return self.url


class KnowledgeFile(models.Model):
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.CASCADE,
        related_name="knowledge_files",
        null=True,
        blank=True
    )
    file = models.CharField(max_length=1024)  # Store S3 URL
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_name = models.CharField(max_length=255)
    doc_name = models.CharField(max_length=255, blank=True, null=True)  # For Pinecone metadata
    indexed = models.BooleanField(default=False)  # Flag to indicate if the file has been indexed

    def __str__(self):
        return self.original_name

    def delete(self, *args, **kwargs):
        # No local file deletion needed, handled in view
        super().delete(*args, **kwargs)


class KnowledgeExcel(models.Model):
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.CASCADE,
        related_name="knowledge_excels",
        null=True,
        blank=True
    )
    file = models.CharField(max_length=1024)  # Store S3 URL
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_name = models.CharField(max_length=255)
    excel_name = models.CharField(max_length=255, blank=True, null=True)  # For Pinecone metadata
    indexed = models.BooleanField(default=False)  # Flag to indicate if the file has been indexed

    def __str__(self):
        return self.original_name

    def delete(self, *args, **kwargs):
        # No local file deletion needed, handled in view
        super().delete(*args, **kwargs)


class KnowledgeDataExcel(models.Model):
    knowledge_base = models.ForeignKey(
        'KnowledgeBase',
        on_delete=models.CASCADE,
        related_name="knowledge_data_excels",
        null=True,
        blank=True
    )
    file = models.CharField(max_length=1024)  # Store S3 URL
    uploaded_at = models.DateTimeField(auto_now_add=True)
    original_name = models.CharField(max_length=255)
    summary = models.TextField(blank=True, null=True)  # Summary of the data
    data_excel_name = models.CharField(max_length=255, blank=True, null=True)  # For Pinecone metadata

    def __str__(self):
        return self.original_name

    def delete(self, *args, **kwargs):
        # No local file deletion needed, handled in view
        super().delete(*args, **kwargs)


class TestSuite(models.Model):
    MODE_CHOICES = [
        ("quick", "Quick"),
        ("normal", "Normal"),
        ("extensive", "Extensive"),
    ]
    assistant_config = models.ForeignKey(AssistantConfiguration, on_delete=models.CASCADE, related_name="test_suites")
    mode = models.CharField(max_length=16, choices=MODE_CHOICES)
    test_cases = JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("assistant_config", "mode")

    def __str__(self):
        return f"TestSuite({self.assistant_config_id}, {self.mode})"


class KnowledgeBase(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="knowledge_bases")
    name = models.CharField(max_length=255)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reranking_enabled = models.BooleanField(default=False)  # Flag to indicate if reranking is enabled
    embedding_type = models.CharField(
        max_length=50,
        default="hybrid",
        choices=[("dense", "Dense"), ("hybrid", "Hybrid")]
    )  # Type of embedding
    chunk_size = models.IntegerField(default=1000)  # Size of chunks for processing
    chunk_overlap = models.IntegerField(default=100)  # Overlap size for chunks
    top_k_after_reranking = models.IntegerField(default=5)  # Number of top results to consider for reranking
    top_k = models.IntegerField(default=10)  # Number of top results to return
    sparse_weightage = models.FloatField(default=0.5)  # Weightage for sparse embeddings in hybrid mode
    retrieval_method = models.CharField(
        max_length=50,
        default='dense',
        choices=[('dense', 'Dense'), ('hybrid', 'Hybrid')]
    )  # Retrieval method
    dynamic_links_enabled = models.BooleanField(default=True)  # Flag to indicate if dynamic links are enabled
    update_interval = models.DurationField(default=models.DurationField().to_python("10 00:00:00"))  # Default: 10 days

    def __str__(self):
        return f"{self.name} ({self.uuid})"


class UserTool(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_tools')
    name = models.CharField(max_length=100)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    description = models.TextField()
    endpoint_url = models.URLField(max_length=500)
    http_method = models.CharField(
        max_length=10,
        choices=[
            ('GET', 'GET'),
            ('POST', 'POST'),
            ('PUT', 'PUT'),
            ('DELETE', 'DELETE')
        ]
    )
    headers = models.JSONField(blank=True, null=True, default=dict)
    auth_required = models.BooleanField(default=False)
    auth_type = models.CharField(max_length=20, blank=True, null=True)  # e.g., 'bearer', 'basic'
    auth_credentials = models.JSONField(blank=True, null=True, default=dict)  # e.g., {"token": "..."}
    send_body = models.BooleanField(default=False)
    body_schema = models.JSONField(blank=True, null=True, default=dict)  # OpenAPI-style schema
    optimize_response = models.BooleanField(default=False)
    optimize_type = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[('JSON', 'JSON'), ('HTML', 'HTML'), ('TEXT', 'TEXT')]
    )  # 'JSON', 'HTML', 'Text'
    should_truncate_response = models.BooleanField(default=False)
    truncate_limit = models.IntegerField(blank=True, null=True)
    field_containing_data = models.CharField(max_length=100, blank=True, null=True)
    include_fields = models.CharField(max_length=255, blank=True, null=True)
    always_output_data = models.BooleanField(default=False)
    execute_once = models.BooleanField(default=False)
    retry_on_fail = models.BooleanField(default=False)
    max_tries = models.IntegerField(blank=True, null=True)
    wait_between_tries = models.IntegerField(blank=True, null=True)  # in seconds
    on_error = models.TextField(blank=True, null=True)
    body_content_type = models.CharField(max_length=100, blank=True, null=True)
    specify_query_parameters = models.TextField(blank=True, null=True)
    query_parameters_json = models.JSONField(blank=True, null=True, default=dict)
    specify_headers = models.TextField(blank=True, null=True)
    specify_body = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    send_headers = models.BooleanField(default=False)
    send_query_parameters = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.user})"


class Integrations(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_integrations')  # associated user
    name = models.CharField(max_length=20, blank=True, null=True)  # name of integration(eg. shopify, dbhub, googlesheets etc.)
    feature_name = models.CharField(max_length=50)  # tool's name
    details = models.JSONField(default=dict, blank=True, null=True)  # integration specific details, should be same for all the features


class IntegrationFeature(models.Model):
    integration = models.ForeignKey('Integrations', on_delete=models.CASCADE, related_name='features')
    hash = models.CharField(max_length=50, unique=True, blank=True, null=True)  # e.g., '1001'
    is_active = models.BooleanField(default=True)  # in case to enable/disable features
    config = models.JSONField(default=dict, blank=True, null=True)  # per-feature config


class ChatRoom(models.Model):
    session_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    agent = models.ForeignKey('AssistantConfiguration', on_delete=models.CASCADE)  # Assuming an Agent model exists
    customer_id = models.CharField(max_length=255)  # Use session/user identifier
    start_time = models.DateTimeField(auto_now_add=True)
    last_message_time = models.DateTimeField(auto_now=True)
    captured_data = models.JSONField(default=dict, blank=True, null=True)  # For storing any data captured during the session

    def __str__(self):
        return f"Session with {self.customer_id} - {self.start_time}"


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('agent', 'Agent'),
    )

    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    timestamp = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    message = models.TextField()

    def __str__(self):
        return f"{self.timestamp} - {self.role}: {self.message[:30]}"


class Board(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    images = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
