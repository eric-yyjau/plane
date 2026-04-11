# Event Planning Agent Implementation Plan (Using Plane)

This document outlines the strategy to use [Plane](https://plane.so/) as the base UI/Database engine for our Event Planning AI Agent, requiring minimal modifications to Plane's core codebase.

## Phase 1: Deploy Plane on GCP (Completed/In Progress)

The standard, self-hosted Docker version of Plane will be deployed on a GCP Compute Engine VM.

1.  **Infrastructure:** GCP instance is ready.
2.  **Dependencies:** Ensure Docker and Docker Compose are installed.
3.  **Plane Setup:** Run Plane's `setup.sh`, configure `plane.env`, and start services via `docker-compose`.

## Phase 2: The "Agent as a Colleague" Strategy

We map Event Planning concepts to Plane's existing architecture. Instead of modifying Plane, we introduce the AI as a standard Plane user ("Colleague") via a lightweight Sidecar service.

### 1. Concept Mapping (Data Model)
*   **Plane Workspace** = Your overarching agency or account.
*   **Plane Project** = The specific Event (e.g., "Company Retreat 2026").
*   **Plane Issues** = Event Tasks (e.g., "Book caterer", "Send invites").
*   **Plane Modules/Cycles** = Phases of the Event Timeline (e.g., "Phase 1: Venue Setup").
*   **Plane Gantt/Calendar Views** = The Timeline Engine for the event.

### 2. The AI Identity & Interaction
The AI is invited to the Workspace as a standard user (e.g., `ai@domain.com`) with its own API Token.
*   **Dynamic Templates:** When a new Project is created, Plane sends a webhook to the Sidecar. The Agent queries an LLM to generate a structured timeline/task list and populates the project using its API token.
*   **Interactive Mentions:** The Agent listens for `issue_comment.created` webhooks. If `@mentioned`, the Agent reads the context and posts a reply comment directly in the UI.

### 3. Minimal UI Tweaks (Optional/Later Phase)
If terminology needs changing (e.g., "Issues" -> "Tasks"):
*   Modify Plane's frontend translation/locale files.
*   Configure default views to favor Gantt/Calendar over standard Lists.

## Implementation Steps

1.  **Repository Setup:** Initialize this repository to store configuration and the sidecar agent code.
2.  **Plane Configuration:** Store custom `docker-compose.yml` or `plane.env` overrides if necessary (ensuring secrets are excluded).
3.  **Agent Development:** Create the sidecar service directory and basic scaffold.
4.  **Integration:** Configure the webhook and API communication between Plane and the Agent.
