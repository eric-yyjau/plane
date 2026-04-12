import logging
import os
from celery import shared_task
from django.conf import settings
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

AGENT_EMAIL = os.environ.get("AGENT_EMAIL", "agent@ai.local")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

try:
    if GEMINI_API_KEY:
        genai_client = genai.Client(api_key=GEMINI_API_KEY)
    else:
        genai_client = None
except Exception as e:
    logger.warning(f"Failed to initialize Gemini Client for Agent Worker. Error: {e}")
    genai_client = None

def get_agent_user():
    """Retrieve the designated AI Agent User object."""
    from plane.db.models.user import User
    return User.objects.filter(email=AGENT_EMAIL).first()

@shared_task
def process_issue_assignment(issue_id: str, assignee_id: str):
    """
    Triggered when a user is assigned to an Issue. 
    Checks if the assigned user is the AI Agent. If so, reads the issue context and responds.
    """
    from plane.db.models import Issue, IssueComment, State
    from plane.db.models.issue import IssueAssignee

    agent_user = get_agent_user()
    if not agent_user or str(agent_user.id) != assignee_id:
        return  # Not the agent, do nothing

    if not genai_client:
        logger.error("Gemini client is not initialized.")
        return

    try:
        issue = Issue.objects.get(id=issue_id)
        logger.info(f"Agent {AGENT_EMAIL} was assigned to Issue: {issue.name}")

        # Basic context for the LLM
        context = f"Title: {issue.name}\nDescription: {issue.description_html or issue.description_stripped}"
        
        # 1. Decide what to do using Gemini
        prompt = f"""
        You are an autonomous AI Event Planning Agent. You have just been assigned to a new ticket in Plane (our project management software).
        
        Ticket Details:
        {context}
        
        Acknowledge the assignment, briefly state what your next steps are based on the ticket description, and ask any clarifying questions if the instructions are ambiguous.
        Write your response as an HTML formatted comment (using basic <p>, <ul> tags).
        """
        
        response = genai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        reply_text = response.text.replace('```html', '').replace('```', '').strip()
        
        # 2. Post a comment back to the Issue
        IssueComment.objects.create(
            workspace_id=issue.workspace_id,
            project_id=issue.project_id,
            issue=issue,
            actor=agent_user,
            comment_html=f"<div>{reply_text}</div>",
            comment_stripped=reply_text,
            created_by=agent_user,
            updated_by=agent_user
        )
        
        # 3. Update the Issue State to "In Progress" if it's in Todo
        in_progress_state = State.objects.filter(project_id=issue.project_id, group='started').first()
        if in_progress_state and issue.state_id != in_progress_state.id:
            issue.state = in_progress_state
            issue.save()

        logger.info(f"Agent successfully responded to assignment on Issue: {issue.name}")

    except Issue.DoesNotExist:
        logger.error(f"Issue {issue_id} not found.")
    except Exception as e:
        logger.error(f"Agent failed to process assignment: {e}")

@shared_task
def process_issue_comment(comment_id: str):
    """
    Triggered when a comment is posted on an Issue.
    Checks if the comment mentions the Agent or if the Agent is assigned to the Issue.
    """
    from plane.db.models import Issue, IssueComment
    from plane.db.models.issue import IssueAssignee

    agent_user = get_agent_user()
    if not agent_user:
        return

    try:
        comment = IssueComment.objects.select_related('issue').get(id=comment_id)
        
        # Ignore our own comments to prevent infinite loops
        if comment.actor_id == agent_user.id:
            return

        is_assigned = IssueAssignee.objects.filter(issue=comment.issue, assignee=agent_user).exists()
        is_mentioned = "agent@ai.local" in comment.comment_stripped.lower() or "agent" in comment.comment_stripped.lower()
        
        if not (is_assigned or is_mentioned):
            return

        logger.info(f"Agent pinged in comment on Issue: {comment.issue.name}")

        comments = IssueComment.objects.filter(issue=comment.issue).order_by('created_at')
        history = ""
        for c in comments:
            actor_name = c.actor.email if c.actor else "System"
            history += f"{actor_name}: {c.comment_stripped}\n"

        prompt = f"""
        You are an autonomous AI Event Planning Agent working alongside humans.
        
        Issue Title: {comment.issue.name}
        Issue Description: {comment.issue.description_stripped}
        
        Conversation History:
        {history}
        
        The last comment was directed at you or an issue you own. Respond appropriately to the conversation.
        Provide your response in basic HTML format (e.g., <p>, <strong>).
        """
        
        if genai_client:
            response = genai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            reply_text = response.text.replace('```html', '').replace('```', '').strip()
            
            IssueComment.objects.create(
                workspace_id=comment.workspace_id,
                project_id=comment.project_id,
                issue=comment.issue,
                actor=agent_user,
                comment_html=f"<div>{reply_text}</div>",
                comment_stripped=reply_text,
                created_by=agent_user,
                updated_by=agent_user
            )

    except IssueComment.DoesNotExist:
        logger.error(f"Comment {comment_id} not found.")
    except Exception as e:
        logger.error(f"Agent failed to process comment: {e}")
