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


def create_issue_comment_with_activities(issue, agent_user, reply_text):
    from plane.db.models import IssueComment
    from plane.bgtasks.issue_activities_task import issue_activity
    from plane.bgtasks.webhook_task import model_activity
    from plane.api.serializers import IssueCommentSerializer
    import json
    from django.core.serializers.json import DjangoJSONEncoder
    from django.utils import timezone
    
    comment_html = f"<div>{reply_text}</div>"
    
    new_comment = IssueComment.objects.create(
        workspace_id=issue.workspace_id,
        project_id=issue.project_id,
        issue=issue,
        actor=agent_user,
        comment_html=comment_html,
        comment_stripped=reply_text,
        created_by=agent_user,
        updated_by=agent_user
    )
    
    serializer_data = IssueCommentSerializer(new_comment).data
    requested_data = {"comment_html": comment_html}
    
    issue_activity.delay(
        type="comment.activity.created",
        requested_data=json.dumps(serializer_data, cls=DjangoJSONEncoder),
        actor_id=str(agent_user.id),
        issue_id=str(issue.id),
        project_id=str(issue.project_id),
        current_instance=None,
        epoch=int(timezone.now().timestamp()),
    )

    model_activity.delay(
        model_name="issue_comment",
        model_id=str(new_comment.id),
        requested_data=requested_data,
        current_instance=None,
        actor_id=agent_user.id,
        slug=issue.workspace.slug,
        origin=""
    )
    return new_comment



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
        create_issue_comment_with_activities(issue, agent_user, reply_text)
        
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
def process_issue_comment(comment_id: str, is_external_reply: bool = False):
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
        
        # If this was explicitly marked as an external reply, skip the loop checks
        if not is_external_reply:
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
        If you need to contact someone, search for a vendor, or send an email, use your available tools.
        If you use a tool, wait for the result and then summarize the outcome to the user.
        Always provide your final response to the user in basic HTML format (e.g., <p>, <strong>).
        """
        
        if genai_client:
            from .skills.email_skill import send_email, check_unread_replies
            from .skills.call_skill import initiate_phone_call, search_vendor_info
            
            tools = [send_email, check_unread_replies, initiate_phone_call, search_vendor_info]
            
            # Start a chat session to handle multi-turn tool calling
            chat = genai_client.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(
                    tools=tools,
                    temperature=0.7,
                )
            )
            
            # Send the initial prompt
            response = chat.send_message(prompt)
            
            # If Gemini decides to call a tool, we need to execute it and return the result
            while response.function_calls:
                for function_call in response.function_calls:
                    tool_name = function_call.name
                    tool_args = function_call.args
                    
                    logger.info(f"Agent invoked tool: {tool_name} with args: {tool_args}")
                    
                    try:
                        # Dynamically call the python function mapped to the tool name
                        if tool_name == "send_email":
                            # Ensure the subject includes the issue identifier so replies can be matched
                            issue_tag = f"[{comment.issue.project.identifier}-{comment.issue.sequence_id}]"
                            if "subject" in tool_args and issue_tag not in tool_args["subject"]:
                                tool_args["subject"] = f"{issue_tag} {tool_args['subject']}"
                            result = send_email(**tool_args)
                        elif tool_name == "check_unread_replies":
                            result = check_unread_replies(**tool_args)
                        elif tool_name == "initiate_phone_call":
                            result = initiate_phone_call(**tool_args)
                        elif tool_name == "search_vendor_info":
                            result = search_vendor_info(**tool_args)
                        else:
                            result = f"Error: Tool {tool_name} not found."
                            
                        # Send the tool result back to Gemini so it can continue reasoning
                        logger.info(f"Tool {tool_name} returned: {result}")
                        response = chat.send_message(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={"result": result}
                            )
                        )
                    except Exception as tool_e:
                        logger.error(f"Error executing tool {tool_name}: {tool_e}")
                        response = chat.send_message(
                            types.Part.from_function_response(
                                name=tool_name,
                                response={"error": str(tool_e)}
                            )
                        )
            
            reply_text = response.text.replace('```html', '').replace('```', '').strip()
            
            create_issue_comment_with_activities(comment.issue, agent_user, reply_text)

    except IssueComment.DoesNotExist:
        logger.error(f"Comment {comment_id} not found.")
    except Exception as e:
        logger.error(f"Agent failed to process comment: {e}")

@shared_task
def poll_agent_email_replies():
    """
    Periodically checks the AI Agent's inbox for new replies.
    If an email contains an issue identifier (e.g., [PROJ-123]) in the subject,
    it adds the email body as a comment to that issue and triggers the agent to respond.
    """
    from plane.db.models import Issue
    from plane.bgtasks.ai_agent.skills.email_skill import check_unread_replies
    import re
    
    agent_user = get_agent_user()
    if not agent_user:
        return
        
    replies = check_unread_replies()
    if not replies:
        return
        
    for reply in replies:
        subject = reply.get("subject", "")
        sender = reply.get("from", "")
        body = reply.get("body", "")
        
        # Look for [PROJ-123] pattern in the subject
        match = re.search(r'\[([A-Z0-9a-zA-Z]+)-(\d+)\]', subject)
        if match:
            project_identifier = match.group(1)
            sequence_id = match.group(2)
            
            try:
                issue = Issue.objects.get(
                    project__identifier=project_identifier,
                    sequence_id=sequence_id,
                    workspace__isnull=False
                )
                
                reply_text = f"**New Email Reply from {sender}:**\n\n**Subject:** {subject}\n\n{body}"
                
                # Add it as a comment from the agent
                comment = create_issue_comment_with_activities(issue, agent_user, reply_text)
                
                logger.info(f"Agent logged a new email reply for Issue: {project_identifier}-{sequence_id}")
                
                # Make the agent evaluate the new reply autonomously
                process_issue_comment.delay(str(comment.id), is_external_reply=True)
                
            except Issue.DoesNotExist:
                logger.warning(f"Received email for unknown issue {project_identifier}-{sequence_id}")
                pass
        else:
            routed = False
            if genai_client:
                logger.info("Attempting context-based email routing via Gemini.")
                recent_issues = Issue.objects.filter(workspace__isnull=False, state__group__in=['backlog', 'unstarted', 'started']).order_by('-updated_at')[:20]
                issue_list_text = "\n".join([f"ID: {issue.id} | Project: {issue.project.identifier}-{issue.sequence_id} | Title: {issue.name}" for issue in recent_issues])
                
                prompt = f"""
                You are an AI assistant helping to route incoming emails to the correct project management ticket.
                
                Incoming Email:
                From: {sender}
                Subject: {subject}
                Body: {body}
                
                Recent Active Tickets:
                {issue_list_text}
                
                Which Ticket ID does this email belong to based on the context? 
                Respond with ONLY the exact UUID of the ticket. If none match, respond with 'NONE'.
                """
                try:
                    response = genai_client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                    )
                    issue_id_match = response.text.strip()
                    if issue_id_match and issue_id_match != 'NONE':
                        import uuid
                        try:
                            valid_uuid = uuid.UUID(issue_id_match)
                            issue = Issue.objects.get(id=valid_uuid)
                            
                            reply_text = f"**New Email Reply from {sender} (Auto-Routed):**\n\n**Subject:** {subject}\n\n{body}"
                            comment = create_issue_comment_with_activities(issue, agent_user, reply_text)
                            logger.info(f"Agent intelligently routed email to Issue: {issue.name}")
                            process_issue_comment.delay(str(comment.id), is_external_reply=True)
                            routed = True
                        except (ValueError, Issue.DoesNotExist):
                            logger.warning(f"LLM returned invalid or unknown Issue ID: {issue_id_match}")
                except Exception as e:
                    logger.error(f"Failed to use LLM for email routing: {e}")

            if not routed:
                logger.info(f"Ignored unread email with no issue tag and no LLM match: {subject}")
