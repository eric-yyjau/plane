# Event Planning Agent Implementation Plan (Using Plane)

This document outlines the strategy to use [Plane](https://plane.so/) as the base UI/Database engine for our Event Planning AI Agent, requiring minimal modifications to Plane's core codebase.

## Phase 1: Deploy Plane on GCP (Completed)

The standard, self-hosted Docker version of Plane is successfully deployed on a GCP Compute Engine VM.

1.  **Infrastructure:** GCP instance (`instance-openclaw-cloud-1`) provisioned. Boot disk resized to 100GB to accommodate Docker data.
2.  **Plane Setup:** Plane v1.3.0 is running via Docker Compose.
3.  **Security:** Configured Caddy (Plane's proxy) to use Let's Encrypt for automatic HTTPS via `nip.io` (Domain: `https://34.31.27.242.nip.io`).

## Phase 2: The "Agent as a Colleague" Strategy (In Progress)

We map Event Planning concepts to Plane's existing architecture. Instead of modifying Plane, we introduce the AI as a standard Plane user ("Colleague") via a lightweight Sidecar service.

### Current Status
*   **The Sidecar Service:** A FastAPI Python app is built (`agent-sidecar/`) and deployed as a Docker container (`plane-sidecar`) directly on the GCP instance, sharing Plane's internal Docker network (`plane-app_default`).
*   **Dynamic Templates (Implemented):** The sidecar listens for the `project.created` webhook, queries Google Gemini (v2.5 Flash), and dynamically generates tasks, pushing them back into the Plane project via the REST API.

### Setup Instructions for Testing

1.  **Add Gemini Key to Server:**
    SSH into the GCP instance and add your Gemini key to the sidecar's environment file:
    ```bash
    gcloud compute ssh --zone "us-central1-a" "instance-openclaw-cloud-1" --project "openclaw-cloud-489305" --command="nano ~/agent-sidecar/.env"
    ```
    Add: `GEMINI_API_KEY=your_actual_key_here`
    Restart the sidecar: `sudo docker restart plane-sidecar`

2.  **Configure the Webhook in Plane:**
    *   Log into Plane (`https://34.31.27.242.nip.io`).
    *   Navigate to **Workspace Settings** -> **Webhooks**.
    *   Add a new webhook with URL: `http://plane-sidecar:8080/plane-webhook` (This uses the secure internal Docker network).
    *   Select the **Project** event to trigger on `project.created`.

3.  **Test the Flow:**
    Create a new Project in Plane (e.g., "Annual Tech Summit") and write a descriptive summary. The AI Colleague should automatically populate the project with issues!

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
