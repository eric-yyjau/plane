import logging
import os
from typing import Optional
from celery import shared_task
from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

try:
    if GEMINI_API_KEY:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        genai_client = None
except Exception as e:
    logger.warning(f"Failed to initialize Gemini Client. Check API Key. Error: {e}")
    genai_client = None


@shared_task
def generate_event_tasks(project_id: str, creator_id: Optional[str] = None):
    """
    Celery task that generates and populates issues for a newly created event planning project.
    """
    from plane.db.models import Project, Issue, State, WorkspaceMember
    from plane.db.models.user import User

    if not genai_client:
        logger.warning("Gemini API Key is not set or client is not initialized. Skipping task generation.")
        return

    try:
        project = Project.objects.get(id=project_id)
        if not project.description:
            logger.info("Project has no description to generate tasks from.")
            return

        logger.info(f"Asking Gemini to generate tasks for Project: {project.name}")

        prompt = f"""
        You are an expert event planner. A user has just created a new event project in our project management system.
        
        Event Name: {project.name}
        Event Description: {project.description_html or project.description}
        
        Based on the event details provided, generate a list of the 5 most critical tasks that need to be completed to make this event successful. 
        Ensure the tasks are actionable and specific to the type of event described.
        
        You must return the response as pure JSON matching this exact structure:
        {{
            "tasks": [
                {{"name": "Task Title", "description": "Detailed description of what needs to be done."}}
            ]
        }}
        """
        
        # Pydantic schema validation internally via google-genai
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        import json
        plan = json.loads(response.text)
        tasks_data = plan.get("tasks", [])
        
        if not tasks_data:
            logger.warning("Gemini did not return any tasks.")
            return

        # Find the "Todo" or "Backlog" state for this project
        state = State.objects.filter(project_id=project.id, group__in=["backlog", "unstarted"]).first()
        
        # Find the AI Agent user if one exists (or fallback to the project creator)
        created_by = None
        if creator_id:
             created_by = User.objects.filter(id=creator_id).first()

        issues_to_create = []
        for index, task in enumerate(tasks_data):
            issues_to_create.append(
                Issue(
                    workspace_id=project.workspace_id,
                    project=project,
                    name=task.get("name", "Untitled Task")[:255],
                    description_html=f"<p>{task.get('description', '')}</p>",
                    state=state,
                    sort_order=index * 10000,
                    created_by=created_by,
                    updated_by=created_by
                )
            )
            
        if issues_to_create:
            Issue.objects.bulk_create(issues_to_create)
            logger.info(f"Successfully generated and inserted {len(issues_to_create)} issues into Project: {project.name}")

    except Project.DoesNotExist:
         logger.error(f"Project with ID {project_id} does not exist.")
    except Exception as e:
        logger.error(f"Failed to generate event tasks: {e}")
