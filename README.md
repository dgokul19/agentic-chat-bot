# Multi-Agent Chatbot System

A sophisticated multi-agent chatbot system built with Python, LangGraph, and FastAPI. The system features three specialized AI agents orchestrated to handle different types of queries through a streaming WebSocket interface.

## 🌟 Features

- **Multi-Agent Architecture**: Three specialized agents for different domains
  - 🍽️ **Booking Agent**: Restaurant reservations and dining recommendations
  - 🏠 **Properties Agent**: Real estate search and property listings
  - 🎓 **Education Agent**: School search and children profile management

- **Intelligent Routing**: LangGraph-based orchestrator with automatic intent classification
- **Streaming Communication**: Real-time WebSocket streaming for responsive interactions
- **Flexible Memory**: Hybrid Redis/JSON storage (auto-detects environment)
- **LLM Support**: Compatible with both OpenAI and Azure OpenAI

## 🏗️ Architecture

```
User Query → WebSocket → Orchestrator → Intent Classification
                              ↓
                    Route to Appropriate Agent
                              ↓
                    Booking | Properties | Education
                              ↓
                    LLM Processing → Response
                              ↓
                    Memory Storage → Stream to User
```

## 📋 Prerequisites

- Python 3.9+
- OpenAI API key or Azure OpenAI credentials
- Redis (optional, for production)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
cd d:\Projects\AgenticAI\agent-chatbot
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:
- Set `OPENAI_API_KEY` or Azure OpenAI credentials
- Configure `ENVIRONMENT` (development/production)
- Set `LLM_PROVIDER` (openai/azure)

### 3. Start the Server

**Option 1: With virtual environment activated**
```bash
# Activate virtual environment first
venv\Scripts\activate  # On Windows

# Then start the server
python -m uvicorn app.main:app --reload --port 8000
```

**Option 2: Without activating virtual environment**
```bash
# Run directly with venv Python
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The server will start on `http://localhost:8000` with hot-reload enabled.

### 4. Stop the Server

Press `Ctrl+C` in the terminal where the server is running.

### 5. Test the Chatbot

Open `client/test_client.html` in your browser and click "Connect".

## 📁 Project Structure

```
agent-chatbot/
├── app/
│   ├── agents/              # Specialized agents
│   │   ├── base_agent.py
│   │   ├── booking_agent.py
│   │   ├── properties_agent.py
│   │   └── education_agent.py
│   ├── orchestrator/        # LangGraph orchestrator
│   ├── memory/              # Memory management
│   ├── models/              # Pydantic schemas
│   ├── utils/               # LLM client
│   ├── config.py            # Configuration
│   └── main.py              # FastAPI app
├── data/memory/             # Local JSON storage
├── client/                  # Test client
└── requirements.txt
```

## 🔧 Configuration

Key settings in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | development/production | development |
| `LLM_PROVIDER` | openai/azure | openai |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `MODEL_NAME` | Model to use | gpt-4-turbo-preview |
| `REDIS_HOST` | Redis host | localhost |
| `WS_PORT` | WebSocket port | 8000 |

## 💬 Usage Examples

### Restaurant Booking
```
"Find me a restaurant in downtown for dinner tonight"
"Book a table for 4 at 7 PM"
```

### Property Search
```
"Show me 3-bedroom apartments under $2000"
"Find properties near the city center"
```

### Education
```
"Find schools near 94105"
"What are the best elementary schools in the area?"
```

## 🔌 API Endpoints

### WebSocket
- `ws://localhost:8000/ws/{session_id}` - Streaming chat endpoint

### HTTP
- `GET /` - API information
- `GET /health` - Health check

## 🧪 Development

### Memory Management

The system automatically uses:
- **Development**: JSON file storage in `data/memory/`
- **Production**: Redis (when available)

### Adding New Agents

1. Create agent class in `app/agents/`
2. Inherit from `BaseAgent`
3. Implement `process()` and `get_capabilities()`
4. Register in orchestrator

## 📝 License

MIT License

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.


