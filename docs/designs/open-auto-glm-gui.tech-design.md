# Open-AutoGLM GUI - Technical Design

## 1. System Architecture

The GUI acts as a local control plane for the `phone_agent`.

```mermaid
graph TD
    User[User] -->|Browser| WebUI[Vue 3 Web UI]
    WebUI -->|HTTP/WS| APIServer[FastAPI Server]
    APIServer -->|Import| PhoneAgentLib[phone_agent Library]
    PhoneAgentLib -->|ADB/HDC| Device[Mobile Device]
    PhoneAgentLib -->|HTTP| LLM[Model Service (Remote/Local)]
```

## 2. Backend Design (gui/server)

### 2.1 Core Services
1.  **DeviceManager:** Wraps `adb` and `hdc` connections. Maintains a list of active devices.
2.  **AgentRunner:** Manages the `PhoneAgent` instance. Handles the execution loop (Think -> Act -> Observe).
3.  **StreamManager:** Broadcasts logs and screenshots to the frontend via WebSocket.

### 2.3 API Endpoints
- **System:**
    - `GET /health`: Server status.
    - `GET /config`: Get current model/env config.
    - `POST /config`: Update config.
- **Devices:**
    - `GET /devices`: List detected/connected devices.
    - `POST /devices/connect`: Connect to a remote device (WiFi).
    - `POST /devices/select`: Set the active device for the agent.
- **Agent:**
    - `POST /chat`: Send a natural language instruction.
    - `POST /stop`: Stop current execution.
    - `GET /history`: Get chat history.
- **Real-time:**
    - `WS /ws/events`: Stream logs, "thought" steps, and execution status.
- **Screen Streaming (HTTP Polling):**
    - `GET /control/stream/latest`: Get the latest screenshot via HTTP polling.
    - `POST /control/stream/settings`: Update stream quality, resolution, FPS.
- **Device Control:**
    - `POST /control/tap`: Simulate tap on device screen.
    - `POST /control/swipe`: Simulate swipe gesture.
    - `POST /control/home`: Press home button.
    - `POST /control/back`: Press back button.
    - `POST /control/recent`: Show recent apps.

## 3. Frontend Design (gui/web)

### 3.1 UI Layout
- **Sidebar:**
    - Device Selector (Dropdown/List).
    - Connection Status Indicator.
    - Navigation (Chat, Settings, Logs).
- **Main Content (Split View):**
    - **Left:** Chat Interface. User types "Open WeChat...", Agent replies with "Thinking..." and "Done".
    - **Right:** Device Screen Mirror. Shows the latest screenshot captured by the agent. Overlays click indicators.
- **Status Bar:** Model selection, API latency.

### 3.2 Key Components
- `DeviceCard`: Shows device info (Battery, IP, ID).
- `ChatBox`: Timeline of user inputs and Agent responses/thoughts.
- `ScreenMirror`: Canvas/Image to display base64 screenshots.
- `ConfigForm`: Form to set API Key, Model URL, Language (CN/EN).

## 4. Data Flow
1.  **Initialization:** Frontend loads, calls `/config` and `/devices`.
2.  **User Action:** User selects device -> calls `/devices/select`.
3.  **Screen Streaming:** Frontend starts HTTP polling loop for screen mirroring:
    - Polls `GET /control/stream/latest` continuously.
    - Uses timestamp validation to ensure frame freshness.
    - Implements "fetch-next-after-display" chaining for flow control.
    - No preloading - only fetch when needed.
4.  **Command:** User types "Check weather" -> `POST /chat`.
5.  **Execution:**
    - Backend `PhoneAgent` starts.
    - Captures Screenshot -> Available via polling endpoint.
    - Sends to LLM -> Receives "Think" -> Emits to WS -> Frontend shows "Thinking".
    - Executes Action -> Emits "Action" -> Frontend shows status.
    - Loop continues until done.

## 5. Security & Constraints
- **Local Access Only:** The server binds to `127.0.0.1` by default.
- **API Keys:** Stored in local `.env` or config file, not exposed to browser storage permanently.
