# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python import
import os
import json
from typing import List, Dict, Tuple

# Third party import
from openai import OpenAI
from google import genai
import requests

from rest_framework import status
from rest_framework.response import Response

# Module import
from plane.app.permissions import ROLE, allow_permission
from plane.app.serializers import ProjectLiteSerializer, WorkspaceLiteSerializer
from plane.db.models import Project, Workspace, Issue, State
from plane.license.utils.instance_value import get_configuration_value
from plane.utils.exception_logger import log_exception

from ..base import BaseAPIView


class LLMProvider:
    """Base class for LLM provider configurations"""

    name: str = ""
    models: List[str] = []
    default_model: str = ""

    @classmethod
    def get_config(cls) -> Dict[str, str | List[str]]:
        return {
            "name": cls.name,
            "models": cls.models,
            "default_model": cls.default_model,
        }


class OpenAIProvider(LLMProvider):
    name = "OpenAI"
    models = ["gpt-3.5-turbo", "gpt-4o-mini", "gpt-4o", "o1-mini", "o1-preview"]
    default_model = "gpt-4o-mini"


class AnthropicProvider(LLMProvider):
    name = "Anthropic"
    models = [
        "claude-3-5-sonnet-20240620",
        "claude-3-haiku-20240307",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-2.1",
        "claude-2",
        "claude-instant-1.2",
        "claude-instant-1",
    ]
    default_model = "claude-3-sonnet-20240229"


class GeminiProvider(LLMProvider):
    name = "Gemini"
    models = ["gemini-pro", "gemini-1.5-pro-latest", "gemini-pro-vision", "gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-3-pro-preview", "gemini-3-flash-preview"]
    default_model = "gemini-3-pro-preview"


SUPPORTED_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
}


def get_llm_config() -> Tuple[str | None, str | None, str | None]:
    """
    Helper to get LLM configuration values, returns:
        - api_key, model, provider
    """
    api_key, provider_key, model = get_configuration_value(
        [
            {
                "key": "LLM_API_KEY",
                "default": os.environ.get("LLM_API_KEY", os.environ.get("GEMINI_API_KEY", None)),
            },
            {
                "key": "LLM_PROVIDER",
                "default": os.environ.get("LLM_PROVIDER", "gemini" if os.environ.get("GEMINI_API_KEY") else "openai"),
            },
            {
                "key": "LLM_MODEL",
                "default": os.environ.get("LLM_MODEL", None),
            },
        ]
    )

    provider = SUPPORTED_PROVIDERS.get(provider_key.lower())
    if not provider:
        log_exception(ValueError(f"Unsupported provider: {provider_key}"))
        return None, None, None

    if not api_key:
        log_exception(ValueError(f"Missing API key for provider: {provider.name}"))
        return None, None, None

    # If no model specified, use provider's default
    if not model:
        model = provider.default_model

    # Validate model is supported by provider
    if model not in provider.models:
        log_exception(
            ValueError(
                f"Model {model} not supported by {provider.name}. Supported models: {', '.join(provider.models)}"
            )
        )
        return None, None, None

    return api_key, model, provider_key


def get_llm_response(task, prompt, api_key: str, model: str, provider: str) -> Tuple[str | None, str | None]:
    """Helper to get LLM completion response"""
    final_text = task + "\n" + prompt
    try:
        if provider.lower() == "gemini":
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=final_text,
            )
            return response.text, None

        # For non-gemini, try OpenAI client
        client = OpenAI(api_key=api_key)
        chat_completion = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": final_text}]
        )
        text = chat_completion.choices[0].message.content
        return text, None
    except Exception as e:
        log_exception(e)
        error_type = e.__class__.__name__
        if error_type == "AuthenticationError":
            return None, f"Invalid API key for {provider}"
        elif error_type == "RateLimitError":
            return None, f"Rate limit exceeded for {provider}"
        else:
            return None, f"Error occurred while generating response from {provider}"



class GPTIntegrationEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        api_key, model, provider = get_llm_config()

        if not api_key or not model or not provider:
            return Response(
                {"error": "LLM provider API key and model are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = request.data.get("task", False)
        if not task:
            return Response({"error": "Task is required"}, status=status.HTTP_400_BAD_REQUEST)

        text, error = get_llm_response(task, request.data.get("prompt", False), api_key, model, provider)
        if not text and error:
            return Response(
                {"error": "An internal error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        workspace = Workspace.objects.get(slug=slug)
        project = Project.objects.get(pk=project_id)

        return Response(
            {
                "response": text,
                "response_html": text.replace("\n", "<br/>"),
                "project_detail": ProjectLiteSerializer(project).data,
                "workspace_detail": WorkspaceLiteSerializer(workspace).data,
            },
            status=status.HTTP_200_OK,
        )


class WorkspaceGPTIntegrationEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        api_key, model, provider = get_llm_config()

        if not api_key or not model or not provider:
            return Response(
                {"error": "LLM provider API key and model are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task = request.data.get("task", False)
        if not task:
            return Response({"error": "Task is required"}, status=status.HTTP_400_BAD_REQUEST)

        text, error = get_llm_response(task, request.data.get("prompt", False), api_key, model, provider)
        if not text and error:
            return Response(
                {"error": "An internal error has occurred."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "response": text,
                "response_html": text.replace("\n", "<br/>"),
            },
            status=status.HTTP_200_OK,
        )


def _extract_json_object(raw_text: str):
    normalized = (raw_text or "").strip()
    if normalized.startswith("```"):
        normalized = normalized.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(normalized)
    except Exception:
        start = normalized.find("{")
        end = normalized.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(normalized[start : end + 1])
            except Exception:
                return None
    return None


class WorkspaceAIChatEndpoint(BaseAPIView):
    @allow_permission(allowed_roles=[ROLE.ADMIN, ROLE.MEMBER], level="WORKSPACE")
    def post(self, request, slug):
        api_key, model, provider = get_llm_config()

        if not api_key or not model or not provider:
            return Response(
                {"error": "LLM provider API key and model are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = request.data.get("message", "").strip()
        if not message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        project_id = request.data.get("project_id", None)
        history = request.data.get("history", [])

        workspace = Workspace.objects.filter(slug=slug).first()
        if not workspace:
            return Response({"error": "Workspace not found"}, status=status.HTTP_404_NOT_FOUND)

        projects = (
            Project.objects.filter(
                workspace__slug=slug,
                project_projectmember__member=request.user,
                project_projectmember__is_active=True,
            )
            .filter(archived_at__isnull=True)
            .distinct()
            .order_by("name")[:15]
        )
        project_context = "\n".join([f"- {project.id}: {project.name}" for project in projects])

        history_text = ""
        if isinstance(history, list):
            for idx, item in enumerate(history[-10:]):
                role = item.get("role", "user")
                content = item.get("content", "")
                history_text += f"{idx + 1}. {role}: {content}\n"

        import datetime
        current_time = datetime.datetime.now().isoformat()

        task = f"""
You are Plane's synchronous AI Assistant for event planning teams.
You can help users brainstorm, schedule meetings, and create tasks.
Current UTC time: {current_time}

Respond as strict JSON with this shape only:
{{
  "reply": "assistant response in plain text",
  "actions": [
    {{
      "type": "create_issue",
      "project_id": "uuid",
      "name": "issue title",
      "description": "issue description"
    }},
    {{
      "type": "schedule_meeting",
      "title": "Meeting Title",
      "start_time": "YYYY-MM-DDTHH:MM:SSZ",
      "end_time": "YYYY-MM-DDTHH:MM:SSZ",
      "attendees": ["email1@example.com"]
    }}
  ]
}}
Rules:
- Keep reply concise and actionable.
- Only return actions if the user clearly requested creating work items or scheduling a meeting.
- For meetings, use the provided time or assume a default 30 min duration. A Google Meet link will be generated automatically.
- Maximum 5 actions.
"""

        prompt = f"""
Workspace: {workspace.name} ({workspace.slug})
Visible projects:
{project_context if project_context else "- No visible projects found"}
Current project_id hint from caller: {project_id}
Recent conversation:
{history_text if history_text else "(none)"}
Latest user message:
{message}
"""

        text, error = get_llm_response(task, prompt, api_key, model, provider)
        if not text or error:
            return Response(
                {"error": "Failed to generate response"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        parsed = _extract_json_object(text)
        if not parsed:
            return Response(
                {
                    "reply": text,
                    "actions_executed": [],
                },
                status=status.HTTP_200_OK,
            )

        reply = (parsed.get("reply") or "").strip() or "I can help with that."
        actions = parsed.get("actions", [])
        if not isinstance(actions, list):
            actions = []

        actions_executed = []

        for action in actions[:5]:
            if action.get("type") == "schedule_meeting":
                import uuid
                title = action.get("title", "Scheduled Meeting")
                start_time = action.get("start_time", "TBD")
                
                # Mock Google Calendar API integration
                # In production, we'd use google-api-python-client here to create an event with conferenceData.
                # For this demo, we generate a realistic Google Meet URL format (xxx-xxxx-xxx)
                meet_id = f"{uuid.uuid4().hex[:3]}-{uuid.uuid4().hex[:4]}-{uuid.uuid4().hex[:3]}"
                meet_link = f"https://meet.google.com/{meet_id}"
                
                actions_executed.append(
                    {
                        "type": "schedule_meeting",
                        "title": title,
                        "start_time": start_time,
                        "meet_link": meet_link,
                        "status": "scheduled",
                    }
                )
                continue

            if action.get("type") != "create_issue":
                continue

            action_project_id = action.get("project_id") or project_id
            if not action_project_id:
                continue

            project = (
                Project.objects.filter(
                    id=action_project_id,
                    workspace__slug=slug,
                    project_projectmember__member=request.user,
                    project_projectmember__is_active=True,
                )
                .filter(archived_at__isnull=True)
                .distinct()
                .first()
            )
            if not project:
                continue

            issue_name = (action.get("name") or "").strip()
            if not issue_name:
                continue

            issue_description = (action.get("description") or "").strip()

            state = State.objects.filter(project_id=project.id, group__in=["backlog", "unstarted"]).first()

            issue = Issue(
                workspace_id=project.workspace_id,
                project=project,
                name=issue_name[:255],
                description_html=f"<p>{issue_description}</p>" if issue_description else "<p></p>",
                state=state,
                created_by=request.user,
                updated_by=request.user,
            )
            issue.save()

            actions_executed.append(
                {
                    "type": "create_issue",
                    "issue_id": str(issue.id),
                    "project_id": str(project.id),
                    "issue_identifier": f"{project.identifier}-{issue.sequence_id}",
                    "name": issue.name,
                }
            )

        return Response(
            {
                "reply": reply,
                "actions_executed": actions_executed,
            },
            status=status.HTTP_200_OK,
        )


class WorkspaceGoogleMeetSummaryEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER])
    def post(self, request, slug, project_id):
        api_key, model, provider = get_llm_config()

        if not api_key:
            return Response(
                {"error": "AI features are not configured for this instance."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        transcript = request.data.get("transcript")
        if not transcript:
            return Response(
                {"error": "Transcript is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = (
            Project.objects.filter(
                id=project_id,
                workspace__slug=slug,
                project_projectmember__member=request.user,
                project_projectmember__is_active=True,
            )
            .filter(archived_at__isnull=True)
            .distinct()
            .first()
        )
        if not project:
            return Response(
                {"error": "Project not found or you don't have access."},
                status=status.HTTP_404_NOT_FOUND,
            )

        task = """
You are an AI assistant for Plane, an event planning and project management tool.
The user has provided a transcript or notes from a Google Meet session.
Your task is to:
1. Summarize the key points of the meeting.
2. Identify all explicit action items.

Respond as strict JSON with this shape only:
{
  "summary": "Detailed summary of the meeting...",
  "actions": [
    {
      "name": "Title of the action item (max 255 chars)",
      "description": "More context or details about the action item"
    }
  ]
}
"""

        prompt = f"""
Transcript/Notes:
{transcript}
"""

        text, error = get_llm_response(task, prompt, api_key, model, provider)
        if not text or error:
            return Response(
                {"error": "Failed to generate response"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        parsed = _extract_json_object(text)
        if not parsed:
            return Response(
                {
                    "summary": "Could not parse the generated summary.",
                    "actions_executed": [],
                },
                status=status.HTTP_200_OK,
            )

        summary = (parsed.get("summary") or "").strip()
        actions = parsed.get("actions", [])
        if not isinstance(actions, list):
            actions = []

        actions_executed = []

        for action in actions[:10]: # Max 10 tasks to prevent abuse
            issue_name = (action.get("name") or "").strip()
            if not issue_name:
                continue

            issue_description = (action.get("description") or "").strip()

            state = State.objects.filter(project_id=project.id, group__in=["backlog", "unstarted"]).first()

            issue = Issue(
                workspace_id=project.workspace_id,
                project=project,
                name=issue_name[:255],
                description_html=f"<p>{issue_description}</p>" if issue_description else "<p></p>",
                state=state,
                created_by=request.user,
                updated_by=request.user,
            )
            issue.save()

            actions_executed.append(
                {
                    "issue_id": str(issue.id),
                    "project_id": str(project.id),
                    "issue_identifier": f"{project.identifier}-{issue.sequence_id}",
                    "name": issue.name,
                }
            )

        return Response(
            {
                "summary": summary,
                "actions_executed": actions_executed,
            },
            status=status.HTTP_200_OK,
        )


class UnsplashEndpoint(BaseAPIView):
    def get(self, request):
        (UNSPLASH_ACCESS_KEY,) = get_configuration_value(
            [
                {
                    "key": "UNSPLASH_ACCESS_KEY",
                    "default": os.environ.get("UNSPLASH_ACCESS_KEY"),
                }
            ]
        )
        # Check unsplash access key
        if not UNSPLASH_ACCESS_KEY:
            return Response([], status=status.HTTP_200_OK)

        # Query parameters
        query = request.GET.get("query", False)
        page = request.GET.get("page", 1)
        per_page = request.GET.get("per_page", 20)

        url = (
            f"https://api.unsplash.com/search/photos/?client_id={UNSPLASH_ACCESS_KEY}&query={query}&page=${page}&per_page={per_page}"
            if query
            else f"https://api.unsplash.com/photos/?client_id={UNSPLASH_ACCESS_KEY}&page={page}&per_page={per_page}"
        )

        headers = {"Content-Type": "application/json"}

        resp = requests.get(url=url, headers=headers)
        return Response(resp.json(), status=resp.status_code)
