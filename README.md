# Chat360 Internship - Agentic AI Backend
<div align="center">

🤖 **Advanced Django-based agentic AI backend system with knowledge base management, multi-service integrations, and real-time processing capabilities**

[![Django](https://img.shields.io/badge/Django-5.2-green.svg)](https://djangoproject.com)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Chat360_Internship-orange.svg)]()

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
git clone https://github.com/YOUR_USERNAME/Chat360_Internship_Agentic-AI.git
cd Chat360_Internship_Agentic-AI

2. Create virtual environment
python -m venv venv
source venv/bin/activate # On Windows: venv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt

4. Set up environment variables
cp .env.example .env

Edit .env with your actual credentials
5. Database setup
python manage.py migrate
python manage.py createsuperuser

6. Run the application
python manage.py runserver

7. Start Celery worker (separate terminal)
celery -A backend worker --loglevel=info

Run with Docker Compose (separate terminal)
docker-compose up --build

text

---

## 🔑 **Environment Configuration**

Create a `.env` file in the root directory:

Essential API Keys
OPENAI_API_KEY=your_openai_api_key
PINECONE_API_KEY=your_pinecone_api_key
JINA_AI_API_KEY=your_jina_ai_key

Database Configuration
POSTGRES_DB=agentic_ai_db
POSTGRES_USER=your_db_user
POSTGRES_PASSWORD=your_secure_password

AWS S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_STORAGE_BUCKET_NAME=your_s3_bucket

Django Configuration
DJANGO_SECRET_KEY=your_django_secret_key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

text

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

## 💼 **Internship Learning Outcomes**

Through this project at **Chat360**, I gained extensive experience in:

- **🏗️ Enterprise Architecture**: Designing scalable backend systems
- **🤖 AI Integration**: Working with OpenAI, LangChain, and vector databases
- **📊 Data Processing**: Handling large-scale document indexing and retrieval
- **🔗 API Development**: Building robust REST APIs with comprehensive documentation
- **⚡ Async Programming**: Implementing efficient task queues and background processing
- **🔒 Security**: Implementing authentication, authorization, and data protection
- **🐳 DevOps**: Containerization, deployment, and monitoring strategies

---

## 🤝 **Contributing**

This project was developed as part of my internship at Chat360. While it's primarily for learning and portfolio purposes, feedback and suggestions are welcome!

---

## 📄 **License**

This project was developed during my Chat360 internship program and serves as a learning portfolio piece.

---

## 📞 **Contact**

**Developed by**: [Your Name]  
**Company**: Chat360  
**Program**: Software Development Internship  
**LinkedIn**: [Your LinkedIn Profile]  
**Email**: [Your Email]

---

<div align="center">
<b>⭐ If you found this project interesting, please consider giving it a star! ⭐</b>
</div>
