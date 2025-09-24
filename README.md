<h1 align="center">Chat360- Agentic AI </h1>
<div align="center">

🤖 **Advanced Django-based agentic AI backend system with knowledge base management, multi-service integrations, and real-time processing capabilities**

[![Django](https://img.shields.io/badge/Django-5.2-green.svg)](https://djangoproject.com)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)

</div>

---

## 🚀 **Project Overview**

This project was developed during my internship at **Chat360** as a comprehensive backend solution for agentic AI applications. The system integrates advanced AI capabilities with robust backend infrastructure, featuring intelligent knowledge base management, multi-platform integrations, and asynchronous task processing.

### **Key Highlights**
- **🧠 Agentic AI System**: Advanced AI agent management with dynamic tool integration
- **📚 Knowledge Base**: Vector database integration with Pinecone for intelligent document retrieval
- **🔗 Multi-Service Integration**: Seamless connectivity with Shopify, Zoho, WhatsApp, and more
- **⚡ Real-time Processing**: Celery-based async task queue for scalable operations
- **📄 Document Intelligence**: Advanced processing for PDF, DOCX, Excel, and web content
- **🔐 Enterprise Security**: Custom Bearer token authentication with role-based access

---

## 🛠️ **Technology Stack**

| Category | Technologies |
|----------|-------------|
| **Backend** | Django 5.2, Django REST Framework |
| **Database** | PostgreSQL, Redis (Cache) |
| **Vector DB** | Pinecone |
| **Task Queue** | Celery + RabbitMQ |
| **AI/ML** | OpenAI GPT, LangChain, Scikit-learn |
| **Cloud** | AWS S3, Docker |
| **Document Processing** | PyPDF2, python-docx, pandas |
| **Integration APIs** | Shopify, Zoho, Jina AI |


---

## ⚙️ **Quick Setup**

### **Prerequisites**
- Python 3.8+
- PostgreSQL
- Redis
- Docker 

### **Installation**

1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/Chat360_Internship_Agentic-AI.git
cd Chat360_Internship_Agentic-AI
cd backend
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate
On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
```bash
cp .env.example .env
```
Edit .env with your actual credentials

5. Database setup
```bash
python manage.py migrate
python manage.py createsuperuser
```

6. Run the application
```bash
python manage.py runserver
```

7. Start Celery worker (separate terminal)
```bash
celery -A backend worker --loglevel=info
```

8. Run with Docker Compose (separate terminal)
```bash
docker-compose up --build
```
---

## 🚀 **Core Features**

### **🤖 Agentic AI System**
- **Dynamic Tool Integration**: 18+ built-in tools for various operations
- **Custom Tool Creation**: User-defined tools with OpenAPI schema support
- **Multi-Agent Workflows**: Parallel and sequential agent execution
- **Context-Aware Processing**: Intelligent conversation management

### **📚 Knowledge Base Management**
- **Vector Search**: Pinecone-powered semantic search
- **Multi-Format Support**: PDF, DOCX, Excel, web scraping
- **Real-time Indexing**: Automatic document processing and embedding
- **Hybrid Retrieval**: Dense + sparse vector search

### **🔗 Platform Integrations**
- **Shopify**: Order tracking, product recommendations, returns
- **Zoho CRM**: Customer data synchronization
- **WhatsApp Business**: Chat analytics and automation
- **Custom APIs**: Flexible webhook-based integrations

---
## Screenshots

<table>
  <tr>
    <td align="center"><strong>Login</strong></td>
    <td align="center"><strong>Register</strong></td>
  </tr>
  <tr>
    <td><img src="https://github.com/AaryanPuri/Chat360_Internship_Agentic-AI/blob/main/screenshots/1.png" alt="Dashboard" width="100%"></td>
    <td><img src="https://github.com/AaryanPuri/Chat360_Internship_Agentic-AI/blob/main/screenshots/2.png" alt="Ask AI" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><strong>Dashboard</strong></td>
    <td align="center"><strong>Receipt Management</strong></td>
  </tr>
  <tr>
    <td><img src="https://github.com/AaryanPuri/Chat360_Internship_Agentic-AI/blob/main/screenshots/3.png" alt="Knowledge Base" width="100%"></td>
    <td><img src="https://github.com/AaryanPuri/Chat360_Internship_Agentic-AI/blob/main/screenshots/4.png" alt="Abilities & Integrations" width="100%"></td>
  </tr>
   <tr>
    <td align="center"><strong>Analytics</strong></td>
    <td align="center"><strong>Export Data</strong></td>
  </tr>
   <tr>
    <td><img src="https://github.com/AaryanPuri/Chat360_Internship_Agentic-AI/blob/main/screenshots/5.png" alt="AI Assistants" width="100%"></td>
    <td><img src="https://github.com/AaryanPuri/Chat360_Internship_Agentic-AI/blob/main/screenshots/6.png" alt="Assets" width="100%"></td>
  </tr>
</table>

---

## 📚 **API Documentation**

Comprehensive API documentation is available in [API_DOCUMENTATION.md](API_DOCUMENTATION.md).

### **Key Endpoints**

| Endpoint | Description |
|----------|-------------|
| `POST /api/analytics/chat/` | AI chat interface |
| `GET /api/analytics/assistants/` | Agent management |
| `POST /api/analytics/knowledgebase/create/` | Create knowledge base |
| `POST /webhook/` | Webhook handler |
| `GET /oauth/zoho/` | Zoho OAuth integration |

---

## 🧪 **Testing**

Run all tests
python manage.py test

Run specific test modules
python manage.py test analytics.tests

With coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report

text

---

## 🏗️ **Development Workflow**

This project follows professional development practices:

- **Pre-commit Hooks**: Automated code formatting and linting
- **Docker Support**: Containerized development environment
- **Comprehensive Logging**: Structured logging with rotation
- **API Documentation**: Auto-generated OpenAPI specifications
- **Error Handling**: Robust exception management and recovery

---

## 📈 **Performance & Scale**

- **Async Processing**: Celery for background tasks
- **Caching Strategy**: Redis-based multi-level caching
- **Database Optimization**: Efficient query patterns and indexing
- **Vector Storage**: Scalable Pinecone integration
- **Load Balancing Ready**: WSGI/ASGI compatible

---

## 📄 **License**

This project was developed during my internship at Chat360.

---

<div align="center">

# 👤 Aaryan Puri

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/aaryan-puri-04923a228/) [![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/AaryanPuri) [![Email](https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:aaryanpuri75@gmail.com)

</div>

