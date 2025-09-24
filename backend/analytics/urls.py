from django.urls import path

from .cache_management import CacheManagement
from .api import (
    AnalyticsChatView,
    AssistantConfigRetrieveWithToolsView,
    RunUserTool,
    UserProfileView,
    AssistantConfigurationView,
    SaveConfigurationView,
    WhatsAppChatView,
    AssistantConfigDuplicateView,
    AssistantConfigExportView,
    AssistantConfigArchiveView,
    ExportAllRoomsExcelView
)
from . import api
from . import knowledgebase
from . import webhookcomponent
from .functions import (
    UserToolListCreateView,
    UserToolDetailView,
    UserToolExecuteView
)
from .integrations import (
    IntegrationsView,
    shopifyView
)
from .assets import S3UploadView, BoardViewSet, BoardImageView

urlpatterns = [
    path('stream/', AnalyticsChatView.as_view(), name='analytics-chat-stream'),
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('assistant/config/', AssistantConfigurationView.as_view(), name='assistant-config'),
    path('knowledgebase/upload/', knowledgebase.knowledgebase_upload_file, name='knowledgebase-upload-file'),
    path('knowledgebase/list/', knowledgebase.knowledgebase_list_files, name='knowledgebase-list-files'),
    path('knowledgebase/delete/<int:excel_id>/', knowledgebase.knowledgebase_delete_file, name='knowledgebase-delete-file'),
    path('knowledgebase/links/', knowledgebase.knowledgebase_list_links, name='knowledgebase-list-links'),
    path('knowledgebase/add-link/', knowledgebase.knowledgebase_add_link, name='knowledgebase-add-link'),
    path('knowledgebase/add-excel/', knowledgebase.knowledgebase_add_excel, name='knowledgebase_add_excel'),
    path('knowledgebase/excels', knowledgebase.knowledgebase_list_excels, name='knowledgebase-list-excels'),
    path(
        'knowledgebase/delete-excel/',
        knowledgebase.knowledgebase_delete_excel,
        name='knowledgebase-delete-excel'
    ),
    path('knowledgebase_delete_link/<int:link_id>/', knowledgebase.knowledgebase_delete_link, name='knowledgebase-delete-link'),
    path('knowledgebase/add-dataexcel/', knowledgebase.knowledge_add_data_excel, name='knowledgebase_add_dataexcel'),
    path(
        'knowledgebase/delete-dataexcel/',
        knowledgebase.knowledge_delete_data_excel,
        name='knowledgebase_delete_dataexcel'
    ),
    path('knowledgebase/dataexcel/', knowledgebase.get_knowledge_data_excel, name='knowledgebase-list-dataexcels'),
    path('save-configuration', SaveConfigurationView.as_view(), name='save_configuration'),
    path('wa-chat/', WhatsAppChatView.as_view(), name='wa_chat'),
    path('assistant/configs/', api.AssistantConfigListView.as_view(), name='assistant-config-list'),
    path('assistant/config/<uuid:uuid>/', api.AssistantConfigRetrieveUpdateView.as_view(), name='assistant-config-detail'),
    path(
        'assistant/config/<uuid:uuid>/delete/',
        api.AssistantConfigSoftDeleteView.as_view(),
        name='assistant-config-soft-delete'
    ),
    path('assistant/config/<uuid:uuid>/duplicate/', AssistantConfigDuplicateView.as_view(), name='assistant-config-duplicate'),
    path('assistant/config/<uuid:uuid>/export/', AssistantConfigExportView.as_view(), name='assistant-config-export'),
    path('assistant/config/<uuid:uuid>/archive/', AssistantConfigArchiveView.as_view(), name='assistant-config-archive'),
    path(
        'assistant/config/<uuid:uuid>/retrieve-with-tools/',
        AssistantConfigRetrieveWithToolsView.as_view(),
        name='assistant-config-retrieve-with-tools'
    ),
    path('assistant/test-suite/', api.get_test_suite, name='get_test_suite'),
    path('assistant/generate-test-suite/', api.generate_test_suite, name='generate_test_suite'),
    path('assistant/update-test-suite/', api.update_test_suite, name='update_test_suite'),
    path('assistant/delete-test-suite/', api.delete_test_suite, name='delete_test_suite'),
    path('assistant/final-prompt/', api.get_final_prompt, name='get_final_prompt'),
    path('assistant/start-test-suite/', api.start_test_suite, name='start_test_suite'),
    path('assistant/test-suite-results/', api.test_suite_results, name='test_suite_results'),
    path(
        'assistant/<uuid:assistant_id>/website-links/',
        api.WebsiteLinkListCreateView.as_view(),
        name='website-link-list-create'
    ),
    path('website-link/<int:pk>/', api.WebsiteLinkUpdateDeleteView.as_view(), name='website-link-update-delete'),
    path('assistant/<uuid:assistant_id>/knowledge-files/', api.KnowledgeFileListView.as_view(), name='knowledge-file-list'),
    path('knowledge-file/<int:pk>/', api.KnowledgeFileDeleteView.as_view(), name='knowledge-file-delete'),
    path('Knowledge-excel/<int:pk>', api.KnowledgeExcelDeleteView.as_view(), name='knowledge-excel-delete'),
    path('index-knowledge-base/', api.IndexDocumentsAPIView.as_view(), name='index-documents'),
    path('create-knowledge-base/', knowledgebase.create_knowledge_base, name='create-knowledge-base'),
    path('update-knowledge-base/<uuid:kb_id>/', knowledgebase.update_knowledge_base, name='update-knowledge-base'),
    path('delete-knowledge-base/<uuid:kb_id>/', knowledgebase.delete_knowledge_base, name='delete-knowledge-base'),
    path("set_assistant_kb/", knowledgebase.set_assistant_kb, name="set_assistant_kb"),
    path('knowledge-bases/', knowledgebase.list_knowledge_bases, name='knowledgebase-list'),
    path('get-task-status/<str:task_id>/', api.get_task_status, name='get-task-status'),

    # User tool CRUD endpoints
    path('user-tools/', UserToolListCreateView.as_view(), name='user-tool-list-create'),
    path('user-tools/<int:pk>/', UserToolDetailView.as_view(), name='user-tool-detail'),
    path('user-tools/<int:pk>/execute/', UserToolExecuteView.as_view(), name='user-tool-execute'),
    path('webhookresponse/', webhookcomponent.WebhooksComponentView.as_view(), name='webhook-response'),
    path('integrations/shopify/', shopifyView.as_view(), name='shopify-integration'),
    path('integrations/', IntegrationsView.as_view(), name='shopify-integration-feature'),
    path('cache/', CacheManagement.as_view(), name='cache-management'),
    path('s3uploadurl/', S3UploadView.as_view(), name='generate-s3-upload-url'),
    path('boards/', BoardViewSet.as_view({'get': 'list'}), name='board-list'),
    path('boards/create/', BoardViewSet.as_view({'post': 'create'}), name='board-create'),
    path('boards/<uuid:pk>/', BoardViewSet.as_view({'get': 'retrieve'}), name='board-detail'),
    path('boards/<uuid:pk>/update/', BoardViewSet.as_view({'put': 'update'}), name='board-update'),
    path('boards/<uuid:pk>/delete/', BoardViewSet.as_view({'delete': 'destroy'}), name='board-delete'),
    path('boards/<uuid:board_id>/images/list/', BoardImageView.as_view(), name='board-image-list'),   # GET
    path('boards/<uuid:board_id>/images/add/', BoardImageView.as_view(), name='board-image-add'),    # POST
    path('boards/<uuid:board_id>/images/update/', BoardImageView.as_view(), name='board-image-update'),  # PUT
    path('boards/<uuid:board_id>/images/delete/', BoardImageView.as_view(), name='board-image-delete'),  # DELETE
]
