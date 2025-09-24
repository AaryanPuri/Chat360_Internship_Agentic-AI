from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile


class APITestSuite(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.client = APIClient()
        self.token_url = '/api/token/'
        self.register_url = '/api/register/'
        self.profile_url = '/api/analytics/user/profile/'
        self.hello_url = '/api/hello/'
        self.stream_url = '/api/stream/'

    def authenticate(self):
        response = self.client.post(self.token_url, {"username": "testuser", "password": "testpass123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        access = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_user_registration(self):
        response = self.client.post(self.register_url, {"username": "newuser", "password": "newpass123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)

    def test_token_generation(self):
        response = self.client.post(self.token_url, {"username": "testuser", "password": "testpass123"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_token_refresh(self):
        response = self.client.post(self.token_url, {"username": "testuser", "password": "testpass123"})
        refresh = response.data['refresh']
        response = self.client.post('/api/token/refresh/', {"refresh": refresh})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_profile_access_requires_auth(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_access_with_auth(self):
        self.authenticate()
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("username", response.data)

    def test_health_check(self):
        response = self.client.get(self.hello_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Hello from Django API!")

    def test_plaintext_streaming(self):
        response = self.client.get(self.stream_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.headers.get('Content-Type'), 'text/plain; charset=utf-8')

    def test_knowledgebase_list(self):
        self.authenticate()
        response = self.client.get('/api/analytics/knowledgebase/list/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("files", response.data)

    def test_upload_knowledge_file_without_auth(self):
        file = SimpleUploadedFile("test.pdf", b"dummy content", content_type="application/pdf")
        response = self.client.post(
            '/api/analytics/knowledgebase/upload/',
            {"file": file, "kb_uuid": "dummy"},
            format='multipart'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_knowledge_file_with_auth(self):
        self.authenticate()
        file = SimpleUploadedFile("test.pdf", b"dummy content", content_type="application/pdf")
        response = self.client.post(
            '/api/analytics/knowledgebase/upload/',
            {"file": file, "kb_uuid": "dummy"},
            format='multipart'
        )
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_save_assistant_config(self):
        self.authenticate()
        payload = {
            "model_uuid": "test-uuid",
            "agentName": "Agent",
            "organisationName": "Org",
            "organisationDescription": "Desc",
            "examples": ["Example 1", "Example 2"],
            "goal": "Test goal"
        }
        response = self.client.post('/api/analytics/save-configuration', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_index_documents(self):
        self.authenticate()
        response = self.client.post('/api/analytics/index-documents/', {"assistant_id": "dummy-id"}, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_generate_test_suite(self):
        self.authenticate()
        response = self.client.post('/api/analytics/assistant/generate-test-suite/', {
            "assistant_uuid": "dummy-uuid",
            "mode": "quick",
            "use_ai": True
        }, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_add_link_to_kb(self):
        self.authenticate()
        payload = {
            "kb_uuid": "dummy",
            "url": "https://example.com",
            "title": "Example",
            "grabber_enabled": True
        }
        response = self.client.post('/api/analytics/knowledgebase/add-link/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_final_prompt(self):
        self.authenticate()
        response = self.client.get('/api/analytics/assistant/final-prompt/?assistant_uuid=dummy-uuid')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_stream_analytics_chat(self):
        self.authenticate()
        payload = {"messages": [{"role": "user", "content": "Hello"}]}
        response = self.client.post('/api/analytics/stream/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_wa_chat(self):
        self.authenticate()
        payload = {"messages": [{"role": "user", "content": "Hi"}], "model_uuid": "dummy-model"}
        response = self.client.post('/api/analytics/wa-chat/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_assistant_configs(self):
        self.authenticate()
        response = self.client.get('/api/analytics/assistant/configs/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_test_suite(self):
        self.authenticate()
        response = self.client.get('/api/analytics/assistant/test-suite/?assistant_uuid=dummy&mode=quick')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_start_test_suite(self):
        self.authenticate()
        payload = {"config": {}, "test_suite": {}, "model_uuid": "dummy-model"}
        response = self.client.post('/api/analytics/assistant/start-test-suite/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_task_status(self):
        self.authenticate()
        response = self.client.get('/api/analytics/get-task-status/dummy-task-id/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_delete_test_suite(self):
        self.authenticate()
        payload = {"assistant_uuid": "dummy-uuid", "mode": "quick"}
        response = self.client.delete('/api/analytics/assistant/delete-test-suite/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST])

    def test_update_test_suite(self):
        self.authenticate()
        payload = {"test_suite_id": 1, "test_cases": ["case 1"]}
        response = self.client.put('/api/analytics/assistant/update-test-suite/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_test_suite_results(self):
        self.authenticate()
        response = self.client.get('/api/analytics/assistant/test-suite-results/dummy-run-id/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_create_knowledge_base(self):
        self.authenticate()
        payload = {"name": "Test KB", "description": "Just a test"}
        response = self.client.post('/api/analytics/create-knowledge-base/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_knowledge_bases(self):
        self.authenticate()
        response = self.client.get('/api/analytics/knowledge-bases/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_set_assistant_kb(self):
        self.authenticate()
        payload = {"assistant_id": "dummy-id", "kb_id": "dummy-kb"}
        response = self.client.post('/api/analytics/set_assistant_kb/', payload, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_delete_knowledge_base(self):
        self.authenticate()
        response = self.client.delete('/api/analytics/delete-knowledge-base/1/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST])

    def test_website_links_get_post(self):
        self.authenticate()
        get_resp = self.client.get('/api/analytics/assistant/dummy-uuid/website-links/')
        self.assertIn(get_resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        post_resp = self.client.post('/api/analytics/assistant/dummy-uuid/website-links/', {
            "url": "https://example.com", "title": "Example"
        }, format='json')
        self.assertIn(post_resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_update_delete_website_link(self):
        self.authenticate()
        put_resp = self.client.put('/api/analytics/website-link/1/', {
            "url": "https://updated.com", "title": "Updated"
        }, format='json')
        self.assertIn(put_resp.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        del_resp = self.client.delete('/api/analytics/website-link/1/')
        self.assertIn(del_resp.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST])

    def test_assistant_knowledge_files(self):
        self.authenticate()
        response = self.client.get('/api/analytics/assistant/dummy-uuid/knowledge-files/')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_delete_knowledge_file(self):
        self.authenticate()
        response = self.client.delete('/api/analytics/knowledge-file/1/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST])

    def test_delete_knowledge_excel(self):
        self.authenticate()
        response = self.client.delete('/api/analytics/Knowledge-excel/1')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_400_BAD_REQUEST])
