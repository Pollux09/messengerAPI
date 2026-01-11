# 💬 Messenger Backend

Modern backend for a real-time messenger built with **FastAPI**.

The project is designed with an async-first approach, JWT authentication, WebSockets for real-time messaging, and a clean, scalable architecture.

---

## 🚀 Tech Stack

- **FastAPI**
- **PostgreSQL + SQLAlchemy**
- **Alembic**
- **JWT (OAuth2 Bearer)**
- **WebSockets**
- **Redis**
- **Docker / Docker Compose**

---

## 🗂 Project Structure

```text
.
├── main.py                 # Application entry point
├── routers/                # API routes (users, chats, auth)
├── models/                 # SQLAlchemy ORM models
├── schemas/                # Pydantic request/response schemas
├── crud/                   # Business logic & DB operations
├── dependencies/           # Dependencies
├── utils/                  # JWT, mail, redis utilities
├── websocketManagers/      # WebSocket connection managers
├── config/                 # Settings, DB, logging
├── alembic/                # Database migrations
├── Dockerfile
├── docker-compose.yml
