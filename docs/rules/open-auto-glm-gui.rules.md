# Open-AutoGLM GUI - Project Rules

## 1. Project Identification
- **Project Name:** Open-AutoGLM GUI
- **Type:** Hybrid (Local Backend + Frontend Dashboard)
- **Classification:**
  - **Frontend:** Management/Control Frontend (Vue 3 + TypeScript)
  - **Backend:** Local Service (Python/FastAPI) wrapping `phone_agent`

## 2. Technology Stack
### Frontend
- **Framework:** Vue 3
- **Language:** TypeScript
- **Build Tool:** Vite
- **State Management:** Pinia
- **UI Library:** Element Plus + Tailwind CSS
- **Communication:** Axios (HTTP) + WebSocket (Real-time logs)

### Backend
- **Framework:** FastAPI (Python)
- **Reasoning:** Seamless integration with existing `phone_agent` Python library.
- **Concurrency:** `asyncio` for non-blocking device IO and model requests.

## 3. Directory Structure
```
Open-AutoGLM/
├── gui/
│   ├── server/           # Backend (FastAPI)
│   │   ├── app.py
│   │   ├── routers/
│   │   └── services/
│   └── web/              # Frontend (Vue 3)
│       ├── src/
│       ├── public/
│       └── package.json
```

## 4. Development Standards
- **API First:** Define Pydantic models for all requests/responses.
- **Strict Typing:** TypeScript for frontend, Type Hints for backend.
- **Linting:** ESLint/Prettier (Frontend), Ruff/Black (Backend).
- **Component Design:** Atomic design principles; separate logic (composables) from UI.
- **HTTP Polling Rules:**
  - No preloading - fetch only when needed
  - Implement "fetch-next-after-display" chaining
  - Use timestamp validation (X-Timestamp header)
  - Limit concurrent requests to 1
  - Clean up blob URLs to prevent memory leaks
  - Implement exponential backoff for errors
- **Performance:** Target 30FPS, <200ms latency, minimal bandwidth usage
