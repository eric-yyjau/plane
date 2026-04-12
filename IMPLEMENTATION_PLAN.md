# Event Planning Agent Implementation Plan (Using Plane)

This document outlines the strategy to use [Plane](https://plane.so/) as the base UI/Database engine for our Event Planning AI Agent, requiring minimal modifications to Plane's core codebase.

## Phase 1: Deploy Plane on GCP (Completed)

The standard, self-hosted Docker version of Plane is successfully deployed on a GCP Compute Engine VM.

1.  **Infrastructure:** GCP instance (`instance-openclaw-cloud-1`) provisioned. Boot disk resized to 100GB to accommodate Docker data.
2.  **Plane Setup:** Plane v1.3.0 is running via Docker Compose.
3.  **Security:** Configured Caddy (Plane's proxy) to use Let's Encrypt for automatic HTTPS via `nip.io` (Domain: `https://34.31.27.242.nip.io`).

## Phase 2: The "Built-In Native" Strategy (Current Architecture)

Based on feedback, we have migrated away from a webhook-based "Sidecar" service in favor of a **deeply integrated, built-in architecture**. We have hard-forked the Plane backend to natively handle Event Planning AI tasks.

### Advantages of the Built-In Architecture
*   **No Webhooks:** Eliminates the need for external proxy routing, SSRF workarounds, and network latency.
*   **Django Native:** Uses Django's `post_save` signals to instantly detect when an Event Project is created.
*   **Celery Async Tasks:** Pushes Gemini API calls to Plane's existing background worker queues so the UI never hangs while waiting for the LLM to generate the event plan.
*   **Direct Database Access:** Populates Tasks (Issues) using the native Django ORM (`Issue.objects.bulk_create()`), avoiding REST API rate limits and authentication hurdles.

### Current Implementation Details
*   **Dependency Added:** Added `google-genai` to `apps/api/requirements.txt`.
*   **The Signal Hook:** Modified `apps/api/plane/db/models/project.py` to trigger a `post_save` signal whenever a new project with a description is created.
*   **The Celery Task:** Created `apps/api/plane/bgtasks/ai_agent/event_tasks.py` which:
    1. Reads the new Project Name and Description.
    2. Prompts `gemini-2.5-flash` to act as an expert Event Planner and output a structured JSON plan of the 5 most critical tasks.
    3. Maps those tasks directly into the `Issue` model and saves them to the database.

### Setup Instructions for Testing (Native Mode)

To run this built-in AI version, you need to compile a custom Docker image of the backend and deploy it to your GCP instance.

1.  **Set the API Key:** Ensure your `.env` file (or `plane.env` on the server) contains:
    `GEMINI_API_KEY="your_api_key_here"`
2.  **Build the Custom Image:**
    On the server, clone your fork and build the backend image from source:
    ```bash
    docker build -t makeplane/plane-backend:custom -f apps/api/Dockerfile.api .
    ```
3.  **Update Deployment:**
    Modify the `docker-compose.yml` to point the `api`, `worker`, and `beat-worker` services to your new `makeplane/plane-backend:custom` image.
4.  **Restart Services:**
    ```bash
    docker-compose up -d
    ```

When you create a project in the UI, the built-in Celery worker will now seamlessly pick up the event and populate the tasks!

## Implementation Steps

1.  **Repository Setup:** Initialize this repository to store configuration and the sidecar agent code.
2.  **Plane Configuration:** Store custom `docker-compose.yml` or `plane.env` overrides if necessary (ensuring secrets are excluded).
3.  **Agent Development:** Create the sidecar service directory and basic scaffold.
4.  **Integration:** Configure the webhook and API communication between Plane and the Agent.
