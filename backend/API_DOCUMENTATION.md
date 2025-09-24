# API Documentation

This document lists all backend API endpoints, their HTTP methods, expected payloads, and response formats for frontend integration.

---

## 1. POST `/api/analytics/stream/`
**Description:** Stream analytics chat responses.
**Payload:**
```json
{
  "messages": [
    {"role": "user", "content": "..."},
    ...
  ]
}
```
**Response:**
Streaming JSON lines with tokens or errors.

---

## 2. GET `/api/analytics/user/profile/`
**Description:** Get current user profile.
**Response:**
```json
{
  "username": "...",
  "first_name": "...",
  "last_name": "...",
  "email": "..."
}
```

---

## 3. GET/PUT `/api/analytics/assistant/config/`
**Description:** Get or update assistant configuration.
**Payload (PUT):**
```json
{
  "agent_name": "...",
  "organisation_name": "...",
  "organisation_description": "...",
  "examples": [...],
  "goal": "..."
}
```
**Response:**
Assistant configuration object.

---

## 4. POST `/api/analytics/knowledgebase/upload/`
**Description:** Upload a file to the knowledge base (stored in S3).
**Payload:** Multipart form-data with `file` and `kb_uuid`.
**Response:**
```json
{
  "id": 123,
  "name": "filename.pdf",
  "s3_url": "https://..."
}
```

---

## 5. POST `/api/analytics/knowledgebase/refresh/<str:filename>/`
**Description:** Refresh a knowledge base file.
**Payload:** Multipart form-data with `file`.
**Response:**
```json
{"message": "File refreshed", "filename": "..."}
```

---

## 6. GET `/api/analytics/knowledgebase/list/`
**Description:** List all knowledge base files for a given kb_uuid.
**Query Params:** `kb_uuid`
**Response:**
```json
{"files": [{"id": 1, "name": "..."}, ...]}
```

---

## 7. DELETE `/api/analytics/knowledgebase/delete/<int:excel_id>/`
**Description:** Delete a knowledge base file by Excel ID.
**Response:**
```json
{"message": "File deleted"}
```

---

## 8. GET `/api/analytics/knowledgebase/links/`
**Description:** List all knowledge base links for a given kb_uuid.
**Query Params:** `kb_uuid`
**Response:**
```json
{"links": [{"id": 1, "url": "...", "title": "...", "created_at": "...", "updated_at": "..."}, ...]}
```

---

## 9. POST `/api/analytics/knowledgebase/add-link/`
**Description:** Add a new link to the knowledge base.
**Payload:**
```json
{"kb_uuid": "...", "url": "...", "title": "...", "grabber_enabled": true}
```
**Response:**
```json
{"id": 1, "url": "...", "title": "...", "created_at": "...", "updated_at": "..."}
```

---

## 10. POST `/api/analytics/knowledgebase/add-excel/`
**Description:** Upload an Excel file to the knowledge base (stored in S3).
**Payload:** Multipart form-data with `file` and `kb_uuid`.
**Response:**
```json
{
  "id": 1,
  "name": "file.xlsx",
  "s3_url": "https://..."
}
```

---

## 11. GET `/api/analytics/knowledgebase/excels`
**Description:** List all Excel files in the knowledge base for a given kb_uuid.
**Query Params:** `kb_uuid`
**Response:**
```json
{"files": [{"id": 1, "name": "..."}, ...]}
```

---

## 12. DELETE `/api/analytics/knowledgebase/delete-excel/<int:excel_id>/`
**Description:** Delete an Excel file by ID.
**Response:**
204 No Content

---

## 13. DELETE `/api/analytics/knowledgebase_delete_link/<int:link_id>/`
**Description:** Delete a knowledge base link by ID.
**Response:**
```json
{"message": "Link deleted"}
```

---

## 14. POST `/api/analytics/save-configuration`
**Description:** Save assistant configuration.
**Payload:**
```json
{
  "model_uuid": "...",
  "agentName": "...",
  "organisationName": "...",
  "organisationDescription": "...",
  "examples": [...],
  "goal": "..."
}
```
**Response:**
```json
{"message": "Configuration saved successfully!", "model_uuid": "..."}
```

---

## 15. POST `/api/analytics/wa-chat/`
**Description:** Chat with WhatsApp assistant.
**Payload:**
```json
{
  "messages": [...],
  "model_uuid": "..."
}
```
**Response:**
```json
{"message": "..."}
```

---

## 16. GET `/api/analytics/assistant/configs/`
**Description:** List all assistant configs for the user.
**Response:**
```json
[{"assistant_name": "...", "updated_at": "...", "assistant_uuid": "..."}, ...]
```

---

## 17. GET/PUT `/api/analytics/assistant/config/<uuid:uuid>/`
**Description:** Get or update a specific assistant config.
**Payload (PUT):** Same as save-configuration.
**Response:** Assistant config object.

---

## 18. POST `/api/analytics/assistant/config/<uuid:uuid>/delete/`
**Description:** Soft delete an assistant config.
**Response:**
```json
{"success": true}
```

---

## 19. GET `/api/analytics/assistant/test-suite/`
**Description:** Get test suite for assistant.
**Query Params:** `assistant_uuid`, `mode`
**Response:** Test suite object or `{ "test_cases": [] }`

---

## 20. POST `/api/analytics/assistant/generate-test-suite/`
**Description:** Generate a test suite.
**Payload:**
```json
{"assistant_uuid": "...", "mode": "quick|normal|extensive", "use_ai": true}
```
**Response:** Test suite object.

---

## 21. PUT `/api/analytics/assistant/update-test-suite/`
**Description:** Update test suite questions.
**Payload:**
```json
{"test_suite_id": 1, "test_cases": [...]}
```
**Response:** Updated test suite object.

---

## 22. DELETE `/api/analytics/assistant/delete-test-suite/`
**Description:** Delete all questions for a mode.
**Payload:**
```json
{"assistant_uuid": "...", "mode": "..."}
```
**Response:**
204 No Content

---

## 23. GET `/api/analytics/assistant/final-prompt/`
**Description:** Get the fully rendered final prompt for an assistant.
**Query Params:** `assistant_uuid`
**Response:**
```json
{"final_prompt": "..."}
```

---

## 24. POST `/api/analytics/assistant/start-test-suite/`
**Description:** Start a test suite run.
**Payload:**
```json
{"config": {...}, "test_suite": {...}, "model_uuid": "..."}
```
**Response:**
```json
{"run_id": "..."}
```

---

## 25. GET `/api/analytics/assistant/test-suite-results/<str:run_id>/`
**Description:** Get test suite run results.
**Response:**
```json
{"results": [...]}
```

---

## 26. GET/POST `/api/analytics/assistant/<uuid:assistant_id>/website-links/`
**Description:** List or add website links for an assistant.
**Payload (POST):**
```json
{"url": "...", "title": "..."}
```
**Response:**
Website link object.

---

## 27. PUT/DELETE `/api/analytics/website-link/<int:pk>/`
**Description:** Update or delete a website link.
**Payload (PUT):**
```json
{"url": "...", "title": "..."}
```
**Response:**
Website link object (PUT), 204 No Content (DELETE)

---

## 28. GET `/api/analytics/assistant/<uuid:assistant_id>/knowledge-files/`
**Description:** List knowledge files for an assistant.
**Response:**
List of knowledge file objects.

---

## 29. DELETE `/api/analytics/knowledge-file/<int:pk>/`
**Description:** Delete a knowledge file by ID.
**Response:**
204 No Content

---

## 30. DELETE `/api/analytics/Knowledge-excel/<int:pk>`
**Description:** Delete a knowledge Excel file by ID.
**Response:**
204 No Content

---

## 31. POST `/api/analytics/index-documents/`
**Description:** Start background indexing of documents.
**Payload:**
```json
{"assistant_id": "..."}
```
**Response:**
```json
{"status": "Indexing started in background", "task_id": "..."}
```

---

## 32. POST `/api/analytics/create-knowledge-base/`
**Description:** Create a new knowledge base.
**Payload:**
```json
{"name": "...", "description": "..."}
```
**Response:**
Knowledge base object.

---

## 33. POST `/api/analytics/update-knowledge-base/<int:kb_id>/`
**Description:** Update a knowledge base.
**Payload:**
```json
{"name": "...", "description": "..."}
```
**Response:**
Knowledge base object.

---

## 34. DELETE `/api/analytics/delete-knowledge-base/<int:kb_id>/`
**Description:** Delete a knowledge base.
**Response:**
```json
{"message": "Knowledge base and namespace deleted"}
```

---

## 35. POST `/api/analytics/set_assistant_kb/`
**Description:** Set the knowledge base for an assistant.
**Payload:**
```json
{"assistant_id": "...", "kb_id": "..."}
```
**Response:**
Status object.

---

## 36. GET `/api/analytics/knowledge-bases/`
**Description:** List all knowledge bases for the authenticated user, including counts of files, links, and excels, plus all KB fields.
**Response:**
```json
[
  {
    "id": 1,
    "uuid": "...",
    "name": "...",
    "created_at": "2025-06-19T12:34:56Z",
    "updated_at": "2025-06-19T12:34:56Z",
    "update_interval": "1:00:00",
    "embedding_type": "...",
    "chunk_size": 512,
    "chunk_overlap": 32,
    "retrieval_method": "dense",
    "reranking_enabled": true,
    "top_k": 5,
    "top_k_after_reranking": 3,
    "sparse_weightage": 0.5,
    "files_count": 2,
    "links_count": 4,
    "excels_count": 1
  },
  ...
]
```

---

## 37. GET `/api/analytics/get-task-status/<str:task_id>/`
**Description:** Get the status of a background task.
**Response:**
```json
{"status": "PENDING|SUCCESS|FAILURE", "result": ...}
```

---

## Additional Project Endpoints

## 38. GET `/api/hello/`
**Description:** Health check endpoint.
**Response:**
```json
{"message": "Hello from Django API!"}
```

---

## 39. GET `/api/stream/`
**Description:** Streams lorem ipsum text (plain text, not JSON).
**Response:**
Plain text stream.

---

## 40. GET `/oauth/zoho`
**Description:** Zoho OAuth callback. Redirects to frontend with status. No direct frontend use.

---

## 41. POST `/api/token/`
**Description:** Obtain JWT access and refresh tokens.
**Payload:**
```json
{"username": "...", "password": "..."}
```
**Response:**
```json
{"refresh": "...", "access": "..."}
```

---

## 42. POST `/api/token/refresh/`
**Description:** Refresh JWT access token.
**Payload:**
```json
{"refresh": "..."}
```
**Response:**
```json
{"access": "..."}
```

---

## 43. POST `/api/register/`
**Description:** Register a new user.
**Payload:**
```json
{"username": "...", "password": "..."}
```
**Response:**
```json
{"message": "User registered successfully."}
```

---

## 44. POST `/api/analytics/knowledgebase/add-dataexcel/`
**Description:** Upload a data Excel file to the knowledge base.
**Payload:** Multipart form-data with `file` and `kb_uuid`.
**Response:**
```json
{
  "id": 1,
  "name": "data.xlsx",
  "s3_url": "https://...",
  "summary": "Info:...\n\nHead:..."
}
```

---

## 45. DELETE `/api/analytics/knowledgebase/delete-dataexcel/<int:data_excel_id>/`
**Description:** Delete a data Excel file from the knowledge base.
**Response:**
```json
{"success": true}
```

---

## 46. POST '/api/analytics/assistant/config/<uuid:uuid>/duplicate/'
**Description:** Creates an exact copy of an existing assistant configuration. The new assistant will have "(Copy)" appended to its name and a new, unique UUID.
**Response:**
{
    "success": true,
    "message": "Assistant configuration duplicated successfully.",
    "data": {
        // Full assistant configuration object of the new copy
    }
}
---

## 47. GET '/api/analytics/assistant/config/<uuid:uuid>/export/'
**Description:** Downloads a JSON file containing the complete configuration for the specified assistant.
**Response:**
A .json file download.
---

## 48. POST '/api/analytics/assistant/config/<uuid:uuid>/archive/'
**Description:** Archives or restores an assistant. An archived assistant is typically hidden from lists and inactive.
**Response:**
{
    "success": true,
    "message": "Assistant configuration archived/restored.",
    "data": {
        // Full assistant configuration object with the updated 'archived_at' status
    }
}
---

## 49. GET/POST '/api/analytics/user-tools/'
**Description:** Lists all custom tools created by the authenticated user or creates a new one.
**Response:**
{
    "name": "My Custom Tool",
    "description": "Fetches customer data from an external CRM.",
    "endpoint_url": "https://api.example.com/customers",
    "http_method": "GET",
    "body_schema": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string", "description": "The ID of the customer"}
        },
        "required": ["customer_id"]
    }
}
A list of UserTool objects (GET) or the newly created UserTool object (POST).
---

## 50. GET/PUT/DELETE '/api/analytics/user-tools/<int:pk>/'
**Description:** Retrieve, update, or delete a specific custom tool by its primary key (pk).
**Response:** The UserTool object (GET/PUT) or 204 No Content (DELETE).

## 51. POST '/api/analytics/user-tools/<int:pk>/execute/'
**Description:** Executes a specific custom tool for testing purposes.
**Response:** 
{
    "arguments": {
        "customer_id": "cust_12345"
    }
}
---

