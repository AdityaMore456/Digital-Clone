# 🧠 Digital Clone Platform

> Create an AI-powered digital version of yourself that answers questions using your own resume, projects, portfolio, and uploaded documents.

A full-stack AI application that allows users to build a personalized Digital Clone using Retrieval-Augmented Generation (RAG). The platform indexes user-provided knowledge, retrieves relevant information for every query, and generates grounded responses using an LLM.

---

# 🚀 Features

### 👤 Clone Creation
- Create a personalized AI assistant.
- Upload your Resume (PDF/DOCX).
- Upload project documents.
- Add Portfolio or GitHub links.
- Store clone-specific information securely.

---

### 📚 Knowledge Base

- Automatic document parsing.
- Text chunking.
- Embedding generation.
- FAISS vector indexing.
- Context-aware retrieval using RAG.

---

### 🤖 AI Chat

- Chat with your Digital Clone.
- Responses are generated only from uploaded knowledge.
- Source citations included with every response.
- Hallucination reduction through retrieval grounding.

---

### 🛡 Safety & Guardrails

- Rate limiting
- Prompt injection protection
- Source-grounded answers
- Content moderation
- Tenant-isolated vector databases

---

### 📊 Dashboard

- Upload new documents
- View uploaded files
- Regenerate embeddings
- Manage clone information

---

# 🏗 Architecture

```
                 +------------------+
                 |   React Frontend |
                 +--------+---------+
                          |
                          |
                     REST API
                          |
                          v
                 +------------------+
                 | FastAPI Backend  |
                 +--------+---------+
                          |
          +---------------+----------------+
          |                                |
          |                                |
          v                                v
   SQLite Database                 FAISS Vector Store
          |                                |
          +---------------+----------------+
                          |
                     Retrieved Context
                          |
                          v
                        LLM
                          |
                          v
                   AI Generated Response
```

---

# 🛠 Tech Stack

## Frontend

- React
- Vite
- JavaScript
- HTML5
- CSS3

---

## Backend

- FastAPI
- Python
- SQLAlchemy
- Uvicorn

---

## Database

- SQLite

---

## Vector Database

- FAISS

---

## AI / ML

- OpenAI API
- Retrieval-Augmented Generation (RAG)
- Text Embeddings
- Semantic Search

---

## Document Processing

- PDF Parsing
- DOCX Parsing
- Text Chunking

---

## Security

- Prompt Guardrails
- Rate Limiting
- Input Validation
- Content Moderation

---

# 📂 Project Structure

```
digital-clone-platform/

│
├── backend/
│   ├── app/
│   │   ├── routers/
│   │   ├── uploads/
│   │   ├── vector_store/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── llm.py
│   │   ├── vectorstore.py
│   │   ├── parsing.py
│   │   ├── security.py
│   │   └── config.py
│   │
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
│
├── setup.sh
├── run.sh
└── README.md
```

---

# ⚙ Installation

## 1. Clone Repository

```bash
git clone <repository-url>

cd digital-clone-platform
```

---

## 2. Backend Setup

```bash
cd backend

python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Configure Environment

Create a `.env` file inside the backend folder.

```
OPENAI_API_KEY=your_api_key_here
```

---

## 4. Frontend Setup

```bash
cd frontend

npm install
```

---

# ▶ Running the Project

## Backend

```bash
cd backend

uvicorn app.main:app --reload
```

Backend runs on

```
http://localhost:8000
```

Swagger Documentation

```
http://localhost:8000/docs
```

---

## Frontend

bash: 
cd frontend

npm run dev


Frontend runs on: http://localhost:5173

---

# 🧠 How It Works

1. User uploads documents.
2. Documents are parsed.
3. Text is split into chunks.
4. Embeddings are generated.
5. Chunks are stored in a FAISS vector database.
6. User asks a question.
7. Similar chunks are retrieved.
8. Retrieved context is sent to the LLM.
9. AI generates a grounded response.
10. Sources are shown alongside the answer.

---

# 📸 Future Improvements

- Voice Clone
- Video Avatar
- LinkedIn API Integration
- PostgreSQL Support
- Authentication (JWT/OAuth)
- Cloud Deployment
- Docker Support
- Multi-language Support
- Streaming Responses
- Conversation Memory

---

# 📈 Current Status

✅ MVP Completed

Implemented:

- Document Upload
- RAG Pipeline
- FAISS Vector Search
- FastAPI Backend
- React Frontend
- AI Chat
- Source Citation
- Clone Dashboard
- Security Guardrails

---

# 🎯 Use Cases

- AI Portfolio Assistant
- Personal Knowledge Base
- Resume Chatbot
- Interview Preparation
- Project Showcase
- Student Digital Profile
- AI Personal Assistant

---

# 📄 License

This project is intended for educational and portfolio purposes.

---

# 👨‍💻 Author

**Aditya More**

AI Engineering | Full Stack Development | Machine Learning