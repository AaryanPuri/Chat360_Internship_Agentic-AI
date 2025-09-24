from rest_framework import serializers
from .models import (
    AssistantConfiguration,
    Board,
    Integrations,
    TestSuite,
    WebsiteLink,
    KnowledgeFile,
    KnowledgeExcel,
    KnowledgeBase,
    UserTool
)
from .tools import (analytics_tools,
                    AGENT_TOOLS,
                    WEBHOOK_TOOLS,
                    INTEGRATION_TOOLS
                    )


class WebsiteLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebsiteLink
        fields = [
            'id', 'knowledge_base', 'url', 'title', 'created_at', 'updated_at',
            'grabber_enabled', 'grabbed', 'update_dynamically', 'hash'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class KnowledgeFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeFile
        fields = ['id', 'file', 'original_name', 'uploaded_at']


class KnowledgeExcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeExcel
        fields = ['id', 'file', 'original_name', 'uploaded_at']


class KnowledgeBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeBase
        fields = [
            'id', 'name', 'uuid', 'created_at', 'updated_at',
            'embedding_type', 'chunk_size', 'chunk_overlap', 'retrieval_method',
            'reranking_enabled', 'top_k', 'top_k_after_reranking', 'sparse_weightage', 'update_interval'
        ]


class KnowledgeDataExcelSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeExcel
        fields = ['id', 'file', 'original_name', 'uploaded_at', 'file', 'excel_name']
        read_only_fields = ['id', 'uploaded_at']


class AssistantConfigurationSerializer(serializers.ModelSerializer):
    website_links = WebsiteLinkSerializer(many=True, read_only=True)
    knowledge_files = KnowledgeFileSerializer(many=True, read_only=True)
    knwledge_excels = KnowledgeExcelSerializer(many=True, read_only=True)
    knowledge_base = serializers.PrimaryKeyRelatedField(queryset=KnowledgeBase.objects.all(), allow_null=True, required=False)
    selected_tools = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True)

    class Meta:
        model = AssistantConfiguration

        exclude = ('is_deleted',)  # Hide is_deleted from API output
        # organisation_name is included by default now

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep.pop('assistant_uuid', None)  # Hide UUID by default
        # Ensure stream_responses is always present and boolean
        rep['stream_responses'] = bool(getattr(instance, 'stream_responses', False))
        rep['enable_emojis'] = bool(getattr(instance, 'enable_emojis', False))
        rep['answer_competitor_queries'] = bool(getattr(instance, 'answer_competitor_queries', False))
        rep['competitor_response_bias'] = getattr(instance, 'competitor_response_bias', 'genuine')
        rep['selected_tools'] = getattr(instance, 'selected_tools', [])
        return rep


class TestSuiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSuite
        fields = '__all__'


class UserToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTool
        fields = [
            'id', 'user', 'name', 'description', 'endpoint_url', 'http_method', 'headers',
            'auth_required', 'auth_type', 'auth_credentials', 'send_body', 'body_schema',
            'optimize_response', 'optimize_type', 'should_truncate_response', 'truncate_limit',
            'field_containing_data', 'include_fields', 'always_output_data', 'execute_once',
            'retry_on_fail', 'max_tries', 'wait_between_tries', 'on_error', 'body_content_type',
            'specify_query_parameters', 'query_parameters_json', 'specify_headers', 'specify_body',
            'send_headers', 'send_query_parameters', 'created_at', 'updated_at', 'uuid'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'user', 'uuid']

    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['user'] = request.user
        return super().create(validated_data)


class ConfigFeatureSerializer(serializers.Serializer):
    class Meta:
        model = Integrations
        fields = '__all__'

    def update(self, instance, validated_data):
        # Allow partial updates and handle JSON/text fields robustly
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class BoardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Board
        fields = ['id', 'name', 'description', 'created_at']


class AssistantConfigurationWithToolsSerializer(serializers.ModelSerializer):
    website_links = WebsiteLinkSerializer(many=True, read_only=True)
    knowledge_files = KnowledgeFileSerializer(many=True, read_only=True)
    knowledge_excels = KnowledgeExcelSerializer(many=True, read_only=True)
    knowledge_base = serializers.PrimaryKeyRelatedField(
        queryset=KnowledgeBase.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = AssistantConfiguration
        exclude = ("is_deleted",)  # Hide is_deleted from API output

    def to_representation(self, instance):
        rep = super().to_representation(instance)

        # Ensure boolean fields are always present
        rep["stream_responses"] = bool(getattr(instance, "stream_responses", False))
        rep["enable_emojis"] = bool(getattr(instance, "enable_emojis", False))
        rep["answer_competitor_queries"] = bool(
            getattr(instance, "answer_competitor_queries", False)
        )
        rep["competitor_response_bias"] = getattr(
            instance, "competitor_response_bias", "genuine"
        )

        # Get tool UUIDs from selected_tools
        tool_uuids = getattr(instance, "selected_tools", [])

        # Fetch UserTool objects
        tools = UserTool.objects.filter(uuid__in=tool_uuids)
        rep["selected_tools"] = UserToolSerializer(tools, many=True).data

        # Serialize knowledge base
        if instance.knowledge_base:
            rep["knowledge_base"] = KnowledgeBaseSerializer(
                instance.knowledge_base
            ).data
        else:
            rep["knowledge_base"] = None

        # Map integration_tools with INTEGRATION_TOOLS
        integration_tools = getattr(instance, "integration_tools", [])
        rep["integration_tools"] = [
            INTEGRATION_TOOLS[tool]
            for tool in integration_tools
            if tool in INTEGRATION_TOOLS
        ]

        return rep