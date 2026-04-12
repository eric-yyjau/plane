# AI Agent Interaction Modes & Skills Requirements

This document outlines the requirements and planned architecture for interacting with the AI Event Planning Agent within the Plane ecosystem.

## Mode 1: Ticket-Based Assignment (The "Asynchronous Colleague")

In this mode, the AI acts as a standard team member. Users can assign work to the AI, and the AI will autonomously execute the work over time, communicating progress through standard Plane issue features.

### 1. Triggers & Inputs
*   **Assignment:** The agent wakes up and begins work when a Plane `Issue` is assigned to its user account (e.g., `agent@ai.local`).
*   **Mentions:** The agent listens for `@mentions` in issue comments to answer questions or take specific directions on a task it is already assigned to.
*   **Context Reading:** Before acting, the agent reads the Issue's title, description, and the entire comment thread to understand the constraints and history.

### 2. Core Agent Skills
To execute event planning tasks (like booking venues or contacting caterers), the agent will be equipped with specialized "Tools" (via Gemini Function Calling):
*   **Skill A: Email Management (Gmail Integration)**
    *   **Action:** The agent can draft and send emails to external vendors or stakeholders using a designated service Gmail account.
    *   **Action:** The agent can poll/read replies to the emails it sent and extract the relevant information (e.g., quotes, availability).
*   **Skill B: Calling & Information Gathering**
    *   **Action:** The agent can initiate phone calls to gather information (potentially leveraging the `phone_call_app` / TTS infrastructure in the workspace).
    *   **Action:** The agent can search the web for vendor contact info, pricing, and reviews.

### 3. Outputs & Progress Tracking
*   **Issue Comments:** The agent will post regular updates in the Issue's comment thread (e.g., *"I have emailed 3 caterers. Waiting for their replies."*).
*   **Issue State Updates:** The agent will move the Issue through the Kanban board (e.g., moving it from `Todo` to `In Progress`, and eventually to `Done` once the vendor is secured).

---

## Mode 2: Direct Chat (The "Synchronous Assistant")

In this mode, users can have a real-time, back-and-forth conversation with the AI without needing to create or assign a specific ticket first.

### 1. UI/UX Paradigm
*   **Separate Window/Widget:** A dedicated chat interface. This could be implemented as a floating "Chat" button in the bottom right of the Plane UI, or a dedicated "AI Assistant" tab in the sidebar.

### 2. Capabilities
*   **Brainstorming:** Users can ask for event themes, budget estimations, or vendor recommendations on the fly.
*   **Data Retrieval:** The chat agent can query the Plane database to answer questions like, *"What is the status of the catering ticket?"* or *"How many tasks are left in the Venue Setup module?"*
*   **Action Execution:** During the chat, the user can say *"That sounds like a good plan, create the tickets for that,"* and the agent will instantly populate the Plane board.

---

## Technical Implementation Strategy (Draft)

1.  **Mode 1 (Backend):** 
    *   Hook into Plane's `IssueAssignee` and `IssueComment` `post_save` Django signals.
    *   Build a Celery task that acts as the "Agent Loop" (Observe -> Think -> Act).
    *   Implement LangChain or native Gemini Tool Calling for the Email and Calling functions.
2.  **Mode 2 (Frontend & API):**
    *   Create a new streaming API endpoint in Django (`/api/v1/ai-chat/`).
    *   Modify the Plane Next.js frontend to include a global Chat UI component that connects to this streaming endpoint.