# Open-AutoGLM GUI - Development Plan

## Phase 1: Foundation & Backend (Days 1-2)
- [ ] **Task 1.1:** Initialize project structure (`gui/server`, `gui/web`).
- [ ] **Task 1.2:** Implement FastAPI Server skeleton.
- [ ] **Task 1.3:** Implement `DeviceManager` service (wrapping `adb`/`hdc` listing).
- [ ] **Task 1.4:** Create `/devices` and `/config` endpoints.
- [ ] **Task 1.5:** Verify Python environment and dependencies.

## Phase 2: Core Agent Integration (Days 2-3)
- [ ] **Task 2.1:** Implement `AgentRunner` service. Integrate `PhoneAgent`.
- [ ] **Task 2.2:** Implement `/chat` endpoint.
- [ ] **Task 2.3:** Implement WebSocket for streaming logs ("Thinking" process) and Screenshots.
- [ ] **Task 2.4:** Test Agent execution loop via API (using Swagger UI).

## Phase 3: Frontend Skeleton & Device Management (Days 3-4)
- [ ] **Task 3.1:** Initialize Vue 3 + Vite + Tailwind project.
- [ ] **Task 3.2:** Build Layout (Sidebar, Main Area).
- [ ] **Task 3.3:** Implement Device Selector and Connection UI.
- [ ] **Task 3.4:** Implement Settings Page (Model Config).

## Phase 4: Chat & Screen Mirroring (Days 4-5)
- [ ] **Task 4.1:** Implement Chat Interface (Message list, Input).
- [ ] **Task 4.2:** Implement Real-time Log rendering (Markdown support).
- [ ] **Task 4.3:** Implement HTTP Polling Screen Mirror (No WebSocket, no preloading).
- [ ] **Task 4.4:** Add "fetch-next-after-display" flow control mechanism.
- [ ] **Task 4.5:** Implement screen interaction (Tap, Swipe, Home, Back, Recent).
- [ ] **Task 4.6:** Add FPS monitoring and quality selection UI.

## Phase 5: Refinement & Packaging (Day 5)
- [ ] **Task 5.1:** Error Handling (Device disconnect, API errors).
- [ ] **Task 5.2:** UI Polish (Dark mode, Animations).
- [ ] **Task 5.3:** Create a startup script (`run_gui.py`) to launch both servers.
- [ ] **Task 5.4:** Update `README.md` with GUI usage instructions.
