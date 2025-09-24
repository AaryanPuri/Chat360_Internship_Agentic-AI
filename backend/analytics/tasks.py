from celery import shared_task
from datetime import datetime
import traceback
import os
from openai import OpenAI
import requests
import io
import string
import boto3
import random

from langchain_openai import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
from .constants import AGENT_SYSTEM_PROMPT
from jinja2 import Template
from .models import AssistantConfiguration
from django.contrib.auth import get_user_model
from .models import (
    KnowledgeBase,
    KnowledgeFile,
    WebsiteLink,
    KnowledgeExcel,
    ChatRoom
)
from .tools import AGENT_TOOLS, INTEGRATION_TOOLS
from .indexing import (
    index_uploaded_documents,
    index_scraped_links_with_jina,
    index_excel_documents,
    scrape_link
)
from urllib.parse import urlparse, urljoin
import linkGrabber
from collections import deque
import pandas as pd
from pinecone import Pinecone
# from more_itertools import chunked
from django.utils import timezone
from backend.settings import logger
from PIL import Image
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
from django.core.files.base import ContentFile
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def normalize_config_keys(config):
    """
    Convert camelCase keys in config dict to snake_case for prompt rendering.
    Args:
        config (dict): The configuration dictionary with camelCase keys.
    Returns:
        dict: A new dictionary with keys converted to snake_case.
    """
    logger.debug("normalize_config_keys called")
    if not isinstance(config, dict):
        logger.debug("normalize_config_keys: config is not a dict, returning as is")
        return config
    mapping = {
        "agentName": "agent_name",
        "organisationName": "organisation_name",
        "organisationDescription": "organisation_description",
        "conversationTone": "conversation_tone",
        "systemInstructions": "system_instructions",
        "modelName": "model_name",
        "maxTokens": "max_tokens",
        "topP": "top_p",
        "frequencyPenalty": "frequency_penalty",
        "streamResponses": "stream_responses",
        "jsonMode": "json_mode",
        "autoToolChoice": "auto_tool_choice",
        "useLastUserLanguage": "use_last_user_language",
        "enableEmojis": "enable_emojis",
        "answerCompetitorQueries": "answer_competitor_queries",
        "competitorResponseBias": "competitor_response_bias",
    }
    new_config = {}
    for k, v in config.items():
        new_config[mapping.get(k, k)] = v
    logger.debug(f"normalize_config_keys returning: {new_config}")
    return new_config


@shared_task
def run_test_task(run_id, idx, config, test_case, model_uuid, user_id=None):
    """
    Run a single test case against the agent API and verify the response.
    Args:
        run_id (str): Unique identifier for the test run.
        idx (int): Index of the test case.
        config (dict): Configuration for the agent.
        test_case (dict): The test case containing question and ideal answer.
        model_uuid (str): UUID of the model to use.
        user_id (int, optional): ID of the user running the test. Defaults to None.
    Returns:
        dict: Result of the test case execution including question, expected answer, agent's answer, and verification result.
    """
    logger.info(f"run_test_task started for run_id={run_id}, idx={idx}, model_uuid={model_uuid}")
    try:
        # Fetch latest config from DB if user_id and model_uuid are provided
        db_config = None
        if user_id and model_uuid:
            User = get_user_model()
            try:
                user = User.objects.get(id=user_id)
                db_config = AssistantConfiguration.objects.filter(
                    user=user,
                    assistant_uuid=model_uuid
                ).order_by("-updated_at").first()
            except Exception:
                db_config = None
        if db_config:
            config = db_config
        else:
            config = normalize_config_keys(config)
        system_prompt = build_final_prompt(config)
        logger.warning(f"Running test case {idx} for model {model_uuid} with config: {config}")
        logger.warning(f"System prompt: {system_prompt}")
        agent_answer = call_agent_api(config, test_case["question"], model_uuid, system_prompt)
        verification, verification_result = response_verification(
            test_case["question"],
            test_case["ideal_answer"],
            agent_answer
        )
    except Exception as e:
        agent_answer = f"[Error: {str(e)}]"
        verification = "fail"
        verification_result = str(e)
    logger.info(f"run_test_task finished for run_id={run_id}, idx={idx}")
    return {
        "idx": idx,
        "question": test_case["question"],
        "expected": test_case["ideal_answer"],
        "agent": agent_answer,
        "verification": verification,
        "verification_result": verification_result,
    }


def build_final_prompt(config):
    """
    Build the final system prompt for the agent based on the configuration.
    Args:
        config (dict): Configuration dictionary containing agent settings.
    Returns:
        str: The final system prompt rendered with the provided configuration.
    """
    logger.debug("build_final_prompt called")

    def get_val(key, default=None):
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    agent_name = get_val("agent_name")
    organisation_name = get_val("organisation_name")
    organisation_description = get_val("organisation_description")
    conversation_tone = get_val("conversation_tone")
    examples = get_val("examples")
    goal = get_val("goal")
    use_last_user_language = get_val("use_last_user_language", True)
    languages = get_val("languages")
    enable_emojis = get_val("enable_emojis", False)
    answer_competitor_queries = get_val("answer_competitor_queries", False)
    competitor_response_bias = get_val("competitor_response_bias", "genuine")
    system_instructions = get_val("system_instructions") or get_val("systemInstructions") or ""
    # selected_tools = get_val("selected_tools") or []

    # --- DataExcel summary logic ---
    data_excel = None
    knowledge_base = get_val("knowledge_base")
    if knowledge_base:

        if isinstance(knowledge_base, KnowledgeBase):
            kb_obj = knowledge_base
        else:
            try:
                kb_obj = KnowledgeBase.objects.get(pk=knowledge_base).first()
            except Exception:
                kb_obj = None
        if kb_obj:
            data_excels = kb_obj.knowledge_data_excels.all()
            if data_excels.exists():
                data_excel = "\n\n".join([f"{de.original_name}:\n{de.summary}" for de in data_excels if de.summary])

    selected_tools = []

    # Append AGENT_TOOLS
    for tool in AGENT_TOOLS:
        func = tool.get("function", {})
        name = func.get("name")
        description = func.get("description", "")
        selected_tools.append({
            "name": name,
            "description": description
        })

    # Append INTEGRATION_TOOLS
    integration_tool_ids = get_val("integration_tools", [])
    for tool_id in integration_tool_ids:
        tool = INTEGRATION_TOOLS.get(tool_id)
        if tool:
            func = tool.get("function", {})
            selected_tools.append({
                "name": func.get("name"),
                "description": func.get("description", "")
            })

    context = {
        "agent_name": agent_name,
        "organisation_name": organisation_name,
        "organisation_description": organisation_description if organisation_description != "None" else None,
        "conversation_tone": conversation_tone if conversation_tone not in (None, "None") else None,
        "examples": examples if examples and examples != "None" else None,
        "goal": goal if goal and goal != "None" else None,
        "use_last_user_language": use_last_user_language,
        "languages": languages,
        "enable_emojis": enable_emojis,
        "answer_competitor_queries": answer_competitor_queries,
        "competitor_response_bias": competitor_response_bias,
        "system_instructions": system_instructions,
        "data_excel": data_excel,
        "selected_tools": selected_tools  # add selected_tools here
    }

    system_prompt_template = AGENT_SYSTEM_PROMPT
    system_prompt = Template(system_prompt_template).render(**context).strip()
    # Insert few-shot examples as user/assistant pairs if present
    if examples and isinstance(examples, list) and len(examples) > 0:
        fewshot = "\n".join(
            [
                f"user: {ex.get('question', '')}\nassistant: {ex.get('answer', '')}"
                for ex in examples if ex.get('question') and ex.get('answer')
            ]
        )
        system_prompt = f"{fewshot}\n" + system_prompt
    logger.debug(f"build_final_prompt returning system_prompt of length {len(system_prompt)}")
    return system_prompt


def build_prompt_webhook(config):
    """
    Build the system prompt for webhook component, including response schema instructions and tool usage.
    Args:
        config (dict): Configuration dictionary containing agent settings.
    Returns:
        str: The system prompt rendered with the provided configuration and webhook response schema.
    """
    logger.debug("build_prompt_webhook called")

    def get_val(key, default=None):
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    agent_name = get_val("agent_name")
    organisation_name = get_val("organisation_name")
    organisation_description = get_val("organisation_description")
    conversation_tone = get_val("conversation_tone")
    examples = get_val("examples")
    goal = get_val("goal")
    use_last_user_language = get_val("use_last_user_language", True)
    languages = get_val("languages")
    enable_emojis = get_val("enable_emojis", False)
    answer_competitor_queries = get_val("answer_competitor_queries", False)
    competitor_response_bias = get_val("competitor_response_bias", "genuine")
    system_instructions = get_val("system_instructions") or get_val("systemInstructions") or ""
    # selected_tools = get_val("selected_tools") or []

    # --- DataExcel summary logic ---
    data_excel = None
    knowledge_base = get_val("knowledge_base")
    if knowledge_base:
        if isinstance(knowledge_base, KnowledgeBase):
            kb_obj = knowledge_base
        else:
            try:
                kb_obj = KnowledgeBase.objects.get(pk=knowledge_base).first()
            except Exception:
                kb_obj = None
        if kb_obj:
            data_excels = kb_obj.knowledge_data_excels.all()
            if data_excels.exists():
                data_excel = "\n\n".join([f"{de.original_name}:\n{de.summary}" for de in data_excels if de.summary])

    selected_tools = []

    # Append AGENT_TOOLS
    for tool in AGENT_TOOLS:
        func = tool.get("function", {})
        name = func.get("name")
        description = func.get("description", "")
        selected_tools.append({
            "name": name,
            "description": description
        })

    # Append INTEGRATION_TOOLS
    integration_tool_ids = get_val("integration_tools", [])
    for tool_id in integration_tool_ids:
        tool = INTEGRATION_TOOLS.get(tool_id)
        if tool:
            func = tool.get("function", {})
            selected_tools.append({
                "name": func.get("name"),
                "description": func.get("description", "")
            })

    context = {
        "agent_name": agent_name,
        "organisation_name": organisation_name,
        "organisation_description": organisation_description if organisation_description != "None" else None,
        "conversation_tone": conversation_tone if conversation_tone not in (None, "None") else None,
        "examples": examples if examples and examples != "None" else None,
        "goal": goal if goal and goal != "None" else None,
        "use_last_user_language": use_last_user_language,
        "languages": languages,
        "enable_emojis": enable_emojis,
        "answer_competitor_queries": answer_competitor_queries,
        "competitor_response_bias": competitor_response_bias,
        "system_instructions": system_instructions,
        "data_excel": data_excel,
        "selected_tools": selected_tools
    }

    system_prompt_template = AGENT_SYSTEM_PROMPT
    system_prompt = Template(system_prompt_template).render(**context).strip()
    # Insert few-shot examples as user/assistant pairs if present
    if examples and isinstance(examples, list) and len(examples) > 0:
        fewshot = "\n".join(
            [
                f"user: {ex.get('question', '')}\nassistant: {ex.get('answer', '')}"
                for ex in examples if ex.get('question') and ex.get('answer')
            ]
        )
        system_prompt = f"{fewshot}\n" + system_prompt
        logger.info(f"system_prompt for webhook : {system_prompt}")

    # Add webhook response schema instruction and tool info
    webhook_schema = """
You have access to the following tool:
- get_relevant_images: Use this tool to retrieve relevant image URLs based on the context and user query. use this tool when images would enhance the response.
- capture_user_data: Use this tool to capture user data which is asked to be captured. where ever it is mentioned in the conversation to maintain the records of conversation.
Take care that the name of the key of data have '@' is prefix, so take care of that for example '@user_name', '@email', etc.
- get_buttons: Use this tool to generate buttons on the basis of conversation. then show these buttons.
if you dont know what buttons to show then use get_buttons tool to generate buttons. in general cases you are instructed what buttons to show then there is no need of this tool.
If any image URLs are present in the response from either 'get_relevant_images' or any tool call (like "Image: <url>"), treat it as an image response and return it using the image response format only.

Always respond in the following JSON format for webhook integration:
{
    "message": "<your reply>",
    "status": <status_code>,
    "number_of_images": <number_of_images>,  # Optional, only if images are included
    "image1": "<image_url_1>",  # Optional, only if images are included
    "image2": "<image_url_2>",  # Optional, only if images are included
    "image3": "<image_url_3>",  # Optional, only if images are included
    "image4": "<image_url_4>",  # Optional, only if images are included
    "image5": "<image_url_5>",  # Optional, only if images are included
    "number_of_buttons": <number_of_buttons>,  # Optional, only if buttons are included
    "button1": "<button_content_1>",  # Optional, only if buttons are included
    "button2": "<button_content_2>",  # Optional, only if buttons are included
    "button3": "<button_content_3>"  # Optional, only if buttons are included
    "button4": "<button_content_4>"  # Optional, only if buttons are included
    "button5": "<button_content_5>"  # Optional, only if buttons are included
}
If you do not need to show images and buttons:
{
    "message": "<your reply>",
    "status": <status_code>,
    "number_of_images": 0,
    "image1": "",
    "image2": "",
    "image3": "",
    "image4": "",
    "image5": "",
    "number_of_buttons": 0,
    "button1": "",
    "button2": "",
    "button3": "",
    "button4": "",
    "button5": ""
}
If you need to show images (max 5):
{
    "message": "<your reply>",
    "status": <status_code>,
    "number_of_images": <number_of_images>,  # Optional, only if images are included
    "image1": "<image_url_1>",  # Optional, only if images are included
    "image2": "<image_url_2>",  # Optional, only if images are included
    "image3": "<image_url_3>",  # Optional, only if images are included
    "image4": "<image_url_4>",  # Optional, only if images are included
    "image5": "<image_url_5>",  # Optional, only if images are included
    "number_of_buttons": 0,
    "button1": "",
    "button2": "",
    "button3": "",
    "button4": "",
    "button5": "",
    "status": <status_code>
}

for example we have to show 2 images then the response would be like this:
{
    "message": "<your reply>",
    "status": <status_code>,
    "number_of_images": 2,
    "image1": "<image_url_1>",
    "image2": "<image_url_2>",
    "image3": "",
    "image4": "",
    "image5": "",
    "number_of_buttons": 0,
    "button1": "",
    "button2": "",
    "button3": "",
    "button4": "",
    "button5": "",
}

for example we have to show 2 buttons(you can show maximum of 5 buttons) then the response would be like this:
{
    "message": "<your reply>",
    "status": <status_code>,
    "number_of_images": 0,
    "image1": "",
    "image2": "",
    "image3": "",
    "image4": "",
    "image5": "",
    "number_of_buttons": 2,
    "button1": "<button_content_1",
    "button2": "<button_content_2",
    "button3": ""
    "button4": "",
    "button5": ""
}

for example you have to take a date time input from user then the response would be like this:
{
    "message": "",
    "status": <status_code>,
    "number_of_images": 0,
    "image1": "",
    "image2": "",
    "image3": "",
    "image4": "",
    "image5": "",
    "number_of_buttons": 0,
    "button1": "",
    "button2": "",
    "button3": "",
    "button4": "",
    "button5": ""
}

there is no need to show the buttons if there are no buttons available, so you can skip this part if there are no buttons available.
you cannot show image and buttons in the same response, so you have to choose one of them based on the context and user query.

Only use these fields. Do not add extra fields. Status codes:
- 201 to continue the conversation(when you are expecting to continue the conversation ),
- 251 to diplay required images if available
- 200 to end the conversation
- 226 to show the buttons(to generate buttons use get_buttons tool)
- 202 to take date time input from user (when you are expecting user input of date time)
- 203 to take location input from user (when you are expecting user input of location)
Do not explain the schema in your reply.
"""
    system_prompt = f"{system_prompt}\n\n{webhook_schema}"
    logger.debug(f"build_prompt_webhook returning system_prompt of length {len(system_prompt)}")
    return system_prompt


def call_agent_api(config, question, model_uuid, system_prompt):
    """
    Call the agent API with the provided configuration and question.
    Args:
        config (dict): Configuration dictionary for the agent.
        question (str): The user question to ask the agent.
        model_uuid (str): UUID of the model to use.
        system_prompt (str): The system prompt to use for the agent.
    Returns:
        str: The agent's response to the question.
    """
    logger.info(f"call_agent_api called for model_uuid={model_uuid}")

    def get_val(key, default=None):
        if isinstance(config, dict):
            return config.get(key, default)
        return getattr(config, key, default)

    system_prompt = build_final_prompt(config)
    examples = get_val("examples") or []
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for ex in examples:
        messages.append({"role": "user", "content": ex["question"]})
        messages.append({"role": "assistant", "content": ex["answer"]})
    messages.append({"role": "user", "content": question})
    model = get_val("modelName") or get_val("model_name") or "gpt-4.1"
    temperature = get_val("temperature", 0.7)
    max_tokens = get_val("maxTokens") or get_val("max_tokens") or 1024
    top_p = get_val("topP") or get_val("top_p") or 0.95
    frequency_penalty = get_val("frequencyPenalty") or get_val("frequency_penalty") or 0
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            frequency_penalty=frequency_penalty,
        )
        logger.info("call_agent_api finished")
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Agent Error: {e}]"


def response_verification(question, expected, agent):
    """
    Verify the agent's response against the expected answer using an LLM.
    Args:
        question (str): The user question.
        expected (str): The expected answer.
        agent (str): The agent's response.
    Returns:
        tuple: A tuple containing the verification result ("pass" or "fail") and an explanation.
    """
    logger.debug("response_verification called")
    prompt = (
        f"""You are an AI test evaluator. Given a user question, the expected answer, and the agent's answer,
        determine if the agent's answer is factually correct, relevant, and helpful.
        Do not require the wording to be identical.
        If the agent's answer covers the intent and information of the expected answer, reply with 'pass'.
        Otherwise, reply with 'fail'.\n
        Question: {question}\nExpected Answer: {expected}\nAgent's Answer: {agent}\n
        Evaluation:"""
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {"role": "system", "content": "You are an AI test evaluator."},
                {"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=128,
        )
        content = response.choices[0].message.content.strip()
        verdict = "fail"
        explanation = content
        if content.lower().startswith("pass"):
            verdict = "pass"
            explanation = content[4:].strip()
        elif content.lower().startswith("fail"):
            verdict = "fail"
            explanation = content[4:].strip()
        logger.debug(f"response_verification verdict: {verdict}, explanation: {explanation}")
        return verdict, explanation
    except Exception as e:
        return "fail", f"[Verification Error: {e}]"


def grab_links_from_website(root_url):
    """
    Grabs all links from a given website URL that match the same domain and scheme.
    Args:
        root_url (str): The root URL of the website to scrape.
    Returns:
        list: A list of unique links found on the website that match the same domain and scheme.
    """
    logger.info(f"grab_links_from_website started for {root_url}")
    logger.debug(f"grab_links_from_website called with root_url={root_url}")
    parsed_root = urlparse(root_url)
    root_scheme = parsed_root.scheme
    root_domain = parsed_root.netloc

    links = linkGrabber.Links(root_url)
    found_links = links.find(duplicates=False, pretty=True)
    logger.info(f"Found {len(found_links)} links on {root_url}")

    domain_links = set()
    for link in found_links:
        href = link.get("href")
        if not href:
            continue

        # Make relative links absolute
        abs_url = urljoin(root_url, href)
        parsed_href = urlparse(abs_url)

        # Restrict to same domain and scheme
        if parsed_href.netloc == root_domain and parsed_href.scheme == root_scheme:
            clean_url = parsed_href.scheme + "://" + parsed_href.netloc + parsed_href.path
            clean_url = clean_url.rstrip("/")  # Remove trailing slash
            domain_links.add(clean_url)

    logger.info(f"Returning {len(domain_links)} domain links for {root_url}")
    logger.info(f"grab_links_from_website finished for {root_url}")
    return list(domain_links)


@shared_task(queue='index_knowledge_base')
def index_knowledge_base_task(
    kb_uuid,
    chunk_size: int = 1000,
    chunk_overlap: int = 50,
    embedding_type: str = "hybrid"
) -> dict:
    """
    Celery task to index a knowledge base by processing uploaded documents, website links, and Excel files.
    Args:
        kb_uuid (str): UUID of the knowledge base to index.
        chunk_size (int): Size of chunks for processing documents.
        chunk_overlap (int): Overlap size for chunks.
        embedding_type (str): Type of embedding to use ("dense", "hybrid").
    Returns:
        dict: A dictionary containing the status of the indexing operation and the knowledge base UUID.
    """
    logger.info(f"index_knowledge_base_task started for kb_uuid={kb_uuid}")
    try:
        kb = KnowledgeBase.objects.get(uuid=kb_uuid)

        # ---Index uploaded documents---
        files = KnowledgeFile.objects.filter(knowledge_base=kb, indexed=False)
        if files.exists():
            index_uploaded_documents(
                kb_id=kb.uuid,
                knowledge_files_queryset=files,
                namespace=str(kb.uuid),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embedding_type=embedding_type
            )

        # ---Index website links---
        initial_links = WebsiteLink.objects.filter(knowledge_base=kb, indexed=False)

        if initial_links.exists():
            all_links = set()  # To track unique URLs
            queue = deque()

            # Initialize queue and all_links with initial root URLs
            for link in initial_links:
                if link.grabber_enabled:
                    all_links.add(link.url)
                    queue.append(link.url)

            while queue:
                current_url = queue.popleft()
                try:
                    grabbed_links = grab_links_from_website(root_url=current_url)
                    logger.info(f"Grabbed {len(grabbed_links)} links from {current_url}")
                    for url in grabbed_links:
                        if url not in all_links:
                            all_links.add(url)
                            queue.append(url)
                            WebsiteLink.objects.create(
                                knowledge_base=kb,
                                url=url,
                                grabbed=True,
                                indexed=False,
                                grabber_enabled=True,
                            )
                except Exception as e:
                    logger.warning(f"Failed to grab links from {current_url}: {str(e)}")

        excels = KnowledgeExcel.objects.filter(knowledge_base=kb, indexed=False)
        if excels.exists():
            # Index Excel files
            for excel in excels:
                try:
                    index_excel_documents(
                        kb.uuid,
                        excel,
                        namespace=str(kb.uuid),
                        chunk_overlap=chunk_overlap,
                        chunk_size=chunk_size,
                        embedding_type=embedding_type
                    )
                except Exception as e:
                    logger.error(f"Error indexing Excel file {excel.original_name}: {str(e)}")
        # Filter all WebsiteLinks which were grabbed and enabled for grabber
        final_links = WebsiteLink.objects.filter(
            knowledge_base=kb,
            grabbed=True,
            grabber_enabled=True,
            indexed=False
        )
        final_links = final_links.union(initial_links)

        index_scraped_links_with_jina(
            kb.uuid,
            final_links,
            namespace=str(kb.uuid),
            chunk_overlap=chunk_overlap,
            chunk_size=chunk_size,
            embedding_type=embedding_type
        )

        logger.info(f"index_knowledge_base_task completed for kb_uuid={kb_uuid}")
        logger.info(f"index_knowledge_base_task finished for kb_uuid={kb_uuid}")
        kb.updated_at = timezone.now()
        kb.save(update_fields=["updated_at"])

        return {"status": "success", "kb_uuid": str(kb.uuid)}

    except Exception as e:
        logger.error(f"Error indexing knowledge base {kb_uuid}: {str(e)}\n{traceback.format_exc()}")
        return {"status": "error", "kb_uuid": str(kb.uuid), "error": str(e)}


@shared_task(queue='update_links')
def update_links():
    """
    Celery task to update links in knowledge bases that have dynamic links enabled.
    It checks if the last update was beyond the specified interval and updates the links accordingly.
    Returns:
        dict: A dictionary containing the status of the update operation and the knowledge base UUID.
    """
    logger.info("update_links started")
    all_kb = KnowledgeBase.objects.filter(dynamic_links_enabled=True)
    logger.info(f"Found {all_kb.count()} knowledge bases with dynamic_links_enabled=True")
    for kb in all_kb:
        logger.info(f"Checking KB {kb.uuid} for update interval")
        if (timezone.now() - kb.updated_at).total_seconds() > kb.update_interval.total_seconds():
            logger.info(f"Updating links for knowledge base {kb.uuid}...")
            # Get all links for the knowledge base
            links = WebsiteLink.objects.filter(knowledge_base=kb, update_dynamically=True)
            logger.warning(f"{links}")
            logger.info(f"Found {len(links)} links to update for KB {kb.uuid}")
            links_to_update = []
            for link in links:
                logger.debug(f"Checking link {link.url} for update")
                try:
                    content, hash = scrape_link(link.url)
                    logger.debug(f"Scraped content for {link.url}, hash: {hash}and current hash: {link.hash}")
                    if hash != link.hash:
                        logger.info(f"Link {link.url} content changed, will update.")
                        links_to_update.append(link)
                        link.updated_at = timezone.now()
                        # delete old vectors of the link from pinecone
                        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
                        index = pc.Index(os.getenv('PINECONE_INDEX'))
                        # Query all chunk IDs for this link.url in metadata
                        query_result = index.query(
                            vector=[0.0] * 1024,
                            filter={"doc_link": {"$eq": link.url}},
                            namespace=str(kb.uuid),
                            top_k=10000,
                            include_values=False
                        )
                        link_chunks = [match["id"] for match in query_result.get("matches", [])]
                        logger.debug(f"Found {len(link_chunks)} chunks to delete for link {link.url}")
                        if link_chunks:
                            index.delete(ids=link_chunks, namespace=str(kb.uuid))
                        link.save()

                except Exception as e:
                    logger.error(f"Error updating link {link.url}: {str(e)}")
                    continue

            logger.info(f"Total links to update for KB {kb.uuid}: {len(links_to_update)}")
            index_scraped_links_with_jina(
                kb.uuid,
                links_to_update,
                namespace=str(kb.uuid),
                chunk_overlap=kb.chunk_overlap,
                chunk_size=kb.chunk_size,
                embedding_type=kb.embedding_type
            )
            kb.updated_at = timezone.now()
            kb.save()
            logger.info(f"Finished updating links for knowledge base {kb.uuid}.")
        else:
            logger.info(f"""
                        Knowledge base {kb.uuid} not require update.
                        Last updated at {kb.updated_at}, interval is {kb.update_interval}.
                        """)
            links_to_update = []
    logger.info("update_links finished")
    logger.info(f"Total links updated: {len(links_to_update)} and links are {links_to_update}")
    return {"status": "success", "kb_uuid": str(kb.uuid)}


def refine_query(query, context):
    """
    Use OpenAI to refine the user query to be more specific and relevant.
    If the query is already specific or asks for all images, do not ask for more details, just return the query as is or make it more precise if possible.
    Never ask the user to clarify or specify categories. If the user says 'all images', just return 'all images' or the original query.
    """
    logger.debug("refine_query called")
    system_prompt = (
        "You are an AI assistant that refines user queries to be more specific and relevant so that the agent can answer it better. "
        "Given a user query and conversation context, return a refined version of the query. "
        "If the user query is already specific or asks for all images, do not ask for more categories, do not ask for clarification, just return the query as is or make it more precise if possible. "
        "Never ask the user to specify more details, never ask for clarification, just do your best to refine or echo the query. "
        "If the user says 'all images', just return 'all images' or the original query."
    )
    user_prompt = (
        f"User Query: {query}\n"
        f"Context: {context}\n"
        "Refined Query:"
    )
    completion = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=128,
        temperature=0.2
    )
    content = completion.choices[0].message.content.strip()
    logger.debug("refine_query finished")
    return content


def get_data_from_excel(file_id, pandas_code):
    """
    Get data from an Excel file by executing arbitrary pandas code on the DataFrame 'df'.
    Args:
        file_id (str): ID of the Excel file to query.
        pandas_code (str): Python pandas code to execute on the DataFrame 'df'.
    Returns:
        dict: The result of the pandas code execution and DataFrame context.
    """
    import io
    import contextlib
    logger.info(f"get_data_from_excel started for file_id={file_id}")
    try:
        excel_file = KnowledgeExcel.objects.get(id=file_id)
        if not excel_file.file:
            raise ValueError("Excel file not found or empty.")

        # Load the Excel file into a pandas DataFrame
        df = pd.read_excel(excel_file.file, engine='openpyxl')

        # Get DataFrame context (head and info)
        buffer = io.StringIO()
        df.info(buf=buffer)
        info_str = buffer.getvalue()
        df_context = f"Head:\n{df.head().to_string(index=False)}\n\nInfo:\n{info_str}"

        # Run the provided pandas code
        local_vars = {"df": df}
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                exec(pandas_code, {}, local_vars)
            code_output = stdout.getvalue().strip()
        except Exception as e:
            code_output = f"Execution error: {e}"

        logger.info(f"get_data_from_excel finished for file_id={file_id}")
        return {
            "context": df_context,
            "output": code_output
        }
    except Exception as e:
        logger.error(f"Error getting data from Excel file {file_id}: {str(e)}")
        return {"error": str(e)}


def remove_prefix_and_suffix(prefix=None, suffix=None, order_number=None):
    if not order_number:
        logger.warning("No order_number provided")
        return None

    order_number = order_number.strip().replace(" ", "")
    prefix = str(prefix or "")
    suffix = str(suffix or "")

    starts_with_prefix = order_number.startswith(prefix) if prefix != '0' else True
    ends_with_suffix = order_number.endswith(suffix) if suffix != '0' else True

    if starts_with_prefix and ends_with_suffix:
        start = len(prefix)
        end = -len(suffix) if suffix else None
        order_id = order_number[start:end]
        logger.info(f"Extracted order number: {order_id}")
        return order_id
    else:
        logger.warning(f"Prefix/suffix did not match: {order_number}")
        return order_number


def get_order_id_by_name(order_name, shopify_domain, access_token, return_gid=False):
    """
    Convert a Shopify order name (e.g., #CH1269360) to its internal ID (e.g., 6821593317661)
    """
    query = gql(f"""
    query {{
        orders(first: 1, query: "name:{order_name}") {{
            edges {{
                node {{
                    id
                    name
                    createdAt
                    displayFulfillmentStatus
                    displayFinancialStatus
                }}
            }}
        }}
    }}
        """)
    logger.info(f"query: {query}")

    transport = RequestsHTTPTransport(
        url=f"https://{shopify_domain}/admin/api/2024-04/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        },
        use_json=True,
    )

    client = Client(transport=transport, fetch_schema_from_transport=False)

    try:
        result = client.execute(query)
        edges = result.get("orders", {}).get("edges", [])
        if edges:
            gid = edges[0]["node"]["id"]  # e.g., gid://shopify/Order/6821593317661
            return gid if return_gid else gid.split("/")[-1]     # extract 6821593317661
        else:
            logger.warning(f"No order found with name: {order_name}")
            return None
    except Exception as e:
        logger.error(f"Error getting order ID by name {order_name}: {e}")
        return None


def order_tracking_with_order_id(order_id, shopify_domain, access_token):
    """
    Fetch a single Shopify order by ID using GraphQL.

    Args:
        order_id (str or int): Shopify Order ID (numeric).
        shopify_domain (str): e.g., "your-store.myshopify.com".
        access_token (str): Admin API access token.

    Returns:
        dict: Order status fields or None if not found.
    """
    query = gql(f"""
    query {{
        order(id: "gid://shopify/Order/{order_id}") {{
            id
            name
            createdAt
            displayFinancialStatus
            displayFulfillmentStatus
            totalPriceSet {{
                shopMoney {{
                    amount
                    currencyCode
                }}
            }}
        }}
    }}
    """)

    logger.info(f"query: {query}")

    transport = RequestsHTTPTransport(
        url=f"https://{shopify_domain}/admin/api/2024-04/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        },
        use_json=True,
    )

    client = Client(transport=transport, fetch_schema_from_transport=False)

    try:
        result = client.execute(query)
        order = result.get("order")
        if not order:
            logger.warning(f"No order status found for order : {order_id}")
            return None

        return {
            "order_number": order["name"],
            "created_at": order["createdAt"],
            "financial_status": order.get("displayFinancialStatus", "N/A"),
            "fulfillment_status": order.get("displayFulfillmentStatus", "unfulfilled"),
            "total_amount": f'{order["totalPriceSet"]["shopMoney"]["amount"]} {order["totalPriceSet"]["shopMoney"]["currencyCode"]}'
        }

    except Exception as e:
        logger.error(f"Error fetching order {order_id}: {e}")
        return None


def get_order_detailed_status(shopify_api_domain, shopify_access_token, order_id):
    """
    Get detailed status information for a specific order using GraphQL.
    """
    try:
        graphql_url = f"https://{shopify_api_domain}/admin/api/2024-04/graphql.json"
        query = """
        query getOrderDetails($id: ID!) {
            order(id: $id) {
                id
                name
                createdAt
                updatedAt
                displayFulfillmentStatus
                displayFinancialStatus
                fulfillmentStatus
                financialStatus
                totalPriceSet {
                    shopMoney {
                        amount
                        currencyCode
                    }
                }
                shippingAddress {
                    address1
                    city
                    province
                    zip
                    country
                }
                fulfillments {
                    id
                    status
                    trackingInfo {
                        company
                        number
                        url
                    }
                    createdAt
                    updatedAt
                }
                transactions {
                    id
                    status
                    kind
                    amount
                    createdAt
                }
                lineItems(first: 50) {
                    edges {
                        node {
                            id
                            title
                            quantity
                            fulfillmentStatus
                        }
                    }
                }
            }
        }
        """
        variables = {
            "id": order_id
        }
        headers = {
            "X-Shopify-Access-Token": shopify_access_token,
            "Content-Type": "application/json"
        }
        response = requests.post(graphql_url, json={
            "query": query,
            "variables": variables
        }, headers=headers)
        if not response.ok:
            logger.error(f"GraphQL request failed with status {response.status_code}")
            return None
        data = response.json()
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return None
        order = data.get("data", {}).get("order")
        if not order:
            return None
        # Format detailed order information
        order_details = {
            "order_id": order["id"],
            "order_number": order["name"],
            "created_on": datetime.strptime(order["createdAt"], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d %H:%M:%S"),
            "updated_on": datetime.strptime(order["updatedAt"], "%Y-%m-%dT%H:%M:%S%z").strftime("%Y-%m-%d %H:%M:%S"),
            "fulfillment_status": order["displayFulfillmentStatus"],
            "financial_status": order["displayFinancialStatus"],
            "total_amount": order["totalPriceSet"]["shopMoney"]["amount"],
            "currency": order["totalPriceSet"]["shopMoney"]["currencyCode"],
            "shipping_address": order["shippingAddress"],
        }

        return order_details
    except Exception as e:
        logger.error(f"Error fetching order details: {e}")
        return None


def get_shopify_orders(shopify_api_domain, shopify_access_token, email):
    """
    Get last 10 orders placed using GraphQL.
    """
    logger.info("Function called to get the orders")
    url = f"https://{shopify_api_domain}/admin/api/2024-04/graphql.json"
    headers = {
        "X-Shopify-Access-Token": shopify_access_token,
        "Content-Type": "application/json"
    }

    query = """
    query getCustomer($email: String!) {
        customers(first: 1, query: $email) {
            edges {
                node {
                    id
                    email
                    firstName
                    lastName
                    orders(first: 10, sortKey: CREATED_AT, reverse: true) {
                        edges {
                            node {
                                id
                                name
                                createdAt
                                displayFinancialStatus
                                displayFulfillmentStatus
                            }
                        }
                    }
                }
            }
        }
    }
    """

    variables = {"email": email.strip().lower()}

    try:
        response = requests.post(url, headers=headers, json={"query": query, "variables": variables})
        response.raise_for_status()
        data = response.json()

        logger.info(f"Response from GraphQL: {data}")

        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            return None

        customer_edges = data.get("data", {}).get("customers", {}).get("edges", [])
        if not customer_edges:
            logger.info("No customer found for the given email")
            return None

        orders = customer_edges[0]["node"]["orders"]["edges"]
        if not orders:
            logger.info("No orders found for the customer")
            return None

        formatted_orders = [
            {
                "order_id": order["node"]["id"],
                "order_number": order["node"]["name"],
                "created_on": datetime.strptime(
                    order["node"]["createdAt"], "%Y-%m-%dT%H:%M:%S%z"
                ).strftime("%Y-%m-%d %H:%M:%S"),
                "financial_status": order["node"]["displayFinancialStatus"],
                "fulfillment_status": order["node"]["displayFulfillmentStatus"]
            }
            for order in orders
        ]

        logger.info(f"Formatted orders: {formatted_orders}")
        return formatted_orders if formatted_orders else None

    except Exception:
        logger.exception("Error in get_shopify_orders_with_customer_email_graphql")
        return None
# order_gid = get_order_id_by_name("#CH12345", domain, token, return_gid=True)
# returns = get_returns_for_order(order_gid, domain, token)


def get_fulfillment_line_items_by_order_id(order_gid, shopify_domain, access_token):
    """
    Get the items associated with an order id for return processing.
    """
    transport = RequestsHTTPTransport(
        url=f"https://{shopify_domain}/admin/api/2025-07/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        },
        use_json=True,
    )

    client = Client(transport=transport, fetch_schema_from_transport=False)

    # Correct query without `edges` on `fulfillments`
    query = gql(f"""
    query {{
        order(id: "{order_gid}") {{
            fulfillments {{
            id
            status
            fulfillmentLineItems(first: 10) {{
                edges {{
                node {{
                    id
                    quantity
                    lineItem {{
                    id
                    title
                    sku
                    }}
                }}
                }}
            }}
            }}
        }}
    }}
    """)

    logger.info(f"query for fulfillment items: {query}")

    try:
        result = client.execute(query)
        fulfillment_line_items = []
        fulfillments = result['order']['fulfillments']

        for fulfillment in fulfillments:
            for item_edge in fulfillment['fulfillmentLineItems']['edges']:
                node = item_edge['node']
                fulfillment_line_items.append({
                    "fulfillmentLineItemId": node["id"],
                    "quantity": node["quantity"],
                    "title": node["lineItem"]["title"],
                    "sku": node["lineItem"]["sku"],
                    "fulfillmentId": fulfillment["id"],
                    "fulfillmentStatus": fulfillment["status"]
                })

        return fulfillment_line_items

    except Exception as e:
        logger.error(f"Error fetching fulfillment line items: {e}")
        return []


def create_shopify_order(store_url, access_token, order_data, options_data=None):
    """
    Create an order on Shopify via the Admin GraphQL API (2025-07).

    Parameters:
        store_url (str): Your Shopify store domain (e.g. "your-shop.myshopify.com").
        access_token (str): Shopify Admin API access token (with write_orders scope).
        order_data (dict): Dictionary matching OrderCreateOrderInput.
        options_data (dict, optional): Dictionary matching OrderCreateOptionsInput.

    Returns:
        dict: Parsed JSON response from Shopify containing the order or userErrors.
    """
    endpoint = f"https://{store_url}/admin/api/2025-07/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

    mutation = """
    mutation orderCreate($order: OrderCreateOrderInput!, $options: OrderCreateOptionsInput) {
      orderCreate(order: $order, options: $options) {
        order {
          id
          name
          createdAt
          statusPageUrl
          totalPriceSet {
            shopMoney {
              amount
              currencyCode
            }
          }
          customer {
            email
            firstName
            lastName
          }
          shippingAddress {
            address1
            city
            province
            country
            zip
          }
        }
        userErrors {
          field
          message
        }
      }
    }
    """

    variables = {
        "order": order_data,
        "options": options_data or {}
    }

    response = requests.post(endpoint, headers=headers, json={"query": mutation, "variables": variables})
    response.raise_for_status()  # Raises an exception for HTTP errors
    return response.json()


def return_processing(
    shop_domain: str,
    access_token: str,
    order_id: str,
    fulfillment_line_item_id: str,   # from backend
    quantity: int = 1,
    return_reason: str = "OTHER",
    notify_customer: bool = False,
    restock: bool = True
):
    logger.info("calling the function for return porcessing")
    """
    Creates and processes a return using Shopify Admin GraphQL API (v2025-07).
    Parameters:
        shop_domain (str): Your Shopify store domain (e.g., 'your-store.myshopify.com')
        access_token (str): Admin API access token
        order_id (str): GID of the order (e.g., 'gid://shopify/Order/...')
        fulfillment_line_item_id (str): GID of the fulfillment line item
        quantity (int): Quantity to return
        return_reason (str): Reason for return (e.g., 'DAMAGED', 'TOO_SMALL', 'OTHER')
        notify_customer (bool): Whether to notify the customer by email
        restock (bool): Whether to restock returned items
    Returns:
        dict: Processed return object from Shopify
    """

    endpoint = f"https://{shop_domain}/admin/api/2025-07/graphql.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_token
    }

    # Step 1: Create the return
    create_mutation = """
    mutation ReturnCreate($input: ReturnInput!) {
        returnCreate(returnInput: $input) {
        userErrors {
            field
            message
        }
        return {
            id
            status
        }
        }
    }
    """

    create_variables = {
        "input": {
            "orderId": order_id,
            "returnLineItems": [
                {
                    "fulfillmentLineItemId": fulfillment_line_item_id,
                    "quantity": quantity,
                    "returnReason": return_reason
                }
            ],
            "notifyCustomer": notify_customer
        }
    }

    create_response = requests.post(
        endpoint, json={"query": create_mutation, "variables": create_variables}, headers=headers
    ).json()

    logger.error(f"Create return response: {create_response}")

    errors = create_response.get("data", {}).get("returnCreate", {}).get("userErrors")
    if errors:
        raise Exception(f"Error in returnCreate: {errors}")

    return_id = create_response["data"]["returnCreate"]["return"]["id"]
    logger.info(f"Return ID associated with the order: {return_id}")

    # Step 2: Process the return (refund and restock)
    process_mutation = """
    mutation ReturnProcess($input: ReturnProcessInput!) {
        returnProcess(input: $input) {
        userErrors {
            field
            message
        }
        return {
            id
            status
            totalQuantity
            refunds {
            edges {
                node {
                id
                amount
                }
            }
            }
        }
        }
    }
    """

    process_variables = {
        "input": {
            "returnId": return_id,
            "restock": restock
        }
    }

    process_response = requests.post(
        endpoint, json={"query": process_mutation, "variables": process_variables}, headers=headers
    ).json()
    logger.info("processing the order for return")
    process_errors = process_response.get("data", {}).get("returnProcess", {}).get("userErrors")
    if process_errors:
        raise Exception(f"Error in returnProcess: {process_errors}")

    return process_response["data"]["returnProcess"]["return"]


def fetch_all_products(shopify_domain, access_token):
    """
    Get all the products from shopify using the regitered email
    """
    all_products = []
    after_cursor = None

    transport = RequestsHTTPTransport(
        url=f"https://{shopify_domain}/admin/api/2024-04/graphql.json",
        headers={
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token
        },
        use_json=True,
    )
    client = Client(transport=transport, fetch_schema_from_transport=False)

    query = gql("""
        query GetProducts($after: String) {
        products(first: 250, after: $after) {
            edges {
            cursor
            node {
                id
                title
                vendor
                bodyHtml
                productType
                createdAt
                description
                handle
                onlineStorePreviewUrl
                onlineStoreUrl
                updatedAt
                publishedAt
                templateSuffix
                tags
                status
                variants(first: 100) {
                edges {
                    node {
                    id
                    title
                    price
                    position
                    inventoryPolicy
                    compareAtPrice
                    createdAt
                    updatedAt
                    taxable
                    barcode
                    sku
                    inventoryQuantity
                    image {
                        id
                    }
                    inventoryItem {
                        id
                    }
                    }
                }
                }
                options(first: 100) {
                id
                name
                position
                values
                }
                priceRange {
                minVariantPrice {
                    amount
                }
                }
                images(first: 100) {
                edges {
                    node {
                    id
                    altText
                    width
                    height
                    src
                    }
                }
                }
            }
            }
            pageInfo {
            hasNextPage
            endCursor
            }
        }
        }
    """)
    logger.info("Starting to fetch all products from Shopify")
    while True:
        try:
            variables = {"after": after_cursor}
            result = client.execute(query, variable_values=variables)
            products = result["products"]

            # logger.info(f"Fetched products: {products}")
            all_products.extend([edge["node"] for edge in products["edges"]])

            if not products["pageInfo"]["hasNextPage"]:
                break

            after_cursor = products["pageInfo"]["endCursor"]

        except Exception as e:
            logger.error(f"Error occurred during fetch: {e}")
            break

    return all_products


def get_room_data(room_id):
    """
    Fetch and merge captured data from ChatRoom and external API for the given room_id.
    Only '@'-prefixed keys from the API response 'content' field are merged.
    External API data takes precedence in case of key conflicts.
    """
    logger.info(f"get_room_data called for room_id={room_id}")
    # Get data from ChatRoom
    try:
        chat_room = ChatRoom.objects.get(session_id=room_id)
        local_data = chat_room.captured_data or {}
    except ChatRoom.DoesNotExist:
        local_data = {}

    # Get data from external API
    api_url = f"https://staging.chat360.io/api/clientwidget_updated/{room_id}/sessionvariables_v1?room_id={room_id}&return_all=true"
    headers = {
        "accept": "application/json, text/plain, */*",
    }
    api_data = {}
    try:
        response = requests.get(api_url, headers=headers, timeout=5)
        response.raise_for_status()
        resp_json = response.json()
        # Extract '@'-prefixed keys from 'content' field
        content = resp_json.get("content", {})
        api_data = {k: v for k, v in content.items() if k.startswith("@")}
    except Exception as e:
        logger.error(f"Error fetching data from external API for room {room_id}: {str(e)}")
        api_data = {}

    # Merge: external API data takes precedence
    merged_data = {**local_data, **api_data}
    return merged_data


def get_product_recommendation(products: list, query: str, history: list = None):
    """
    Returns product recommendations based on user query or conversation history.

    Args:
        products (list): List of product dictionaries.
        query (str): User query string.
        history (list, optional): List of previous conversation turns.

    Returns:
        dict: Response containing recommended products or fallback response.
    """
    logger.info("get_product_recommendation called")
    logger.info(f"Input - query: '{query}', history length: {len(history) if history else 0}")

    if not products or not query:
        logger.error("Missing products or query")
        return {
            "success": False,
            "error": "Missing required fields: products and query",
            "status": 400
        }

    # Step 1: Local filtering using query_products_by_user_input
    matched_output = query_products_by_user_input(products, query)
    logger.info(f"Matched products output: {matched_output}")

    if matched_output.strip():
        return {
            "response": matched_output,
            "status": 200
        }

    logger.warning("No products matched after local filtering, using LLM fallback")

    history = [
        {"role": "user", "content": query},
        {"role": "assistant", "content": matched_output.strip() or "No matching products found."}
    ]

    # Step 2: Fallback prompt for LLM-based product suggestion
    fallback_prompt = (
        "If no exact product match was found for the user's current query, clearly inform the user that the requested product is not available at the moment. "
        "Then, review the user's query and chat history to identify relevant interests or preferences. "
        "Based on that history, suggest alternative products or categories from the available inventory that align with their previous behavior or stated needs."
    )
    fallback_response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": fallback_prompt},
            *history
        ],
        temperature=0
    )
    fallback_message = fallback_response.choices[0].message.content
    logger.info(f"LLM fallback response: {fallback_message}")
    history.append({"role": "assistant", "content": fallback_message})

    return {
        "success": True,
        "type": "fallback",
        "products": None,
        "response": fallback_message,
        "status": 200
    }


def query_products_by_user_input(products, query, top_k=5):
    """
    Used to filter the relevant products from shopify on the basis of user query
    """
    logger.info(f"type(products): {type(products)}")

    # Step 1: Flatten the Shopify product structure
    products = extract_products_from_edges(products)
    logger.info(f"Extracted products after function: {products}")

    final_products = []
    for i, item in enumerate(products):
        title = item.get("title", "")
        description = item.get("description", "") or item.get("bodyHtml", "")
        image = ""
        if item.get("images"):
            image = item["images"][0].get("src", "")
        url = item.get("onlineStorePreviewUrl", "")

        # Handle variants
        variants = []
        for variant in item.get("variants", []):
            variants.append({
                "Variant Title": variant.get("title", ""),
                "Price": variant.get("price", ""),
                "Available": variant.get("inventoryQuantity", 0) > 0
            })

        final_products.append({
            "Product Name": title,
            "Description": description,
            "Image": image,
            "URL": url,
            "Variants": variants
        })

    logger.info(f"Final extracted product list: {final_products}")

    if not final_products:
        return "No products available."

    # Step 2: Create dataframe and full text
    df = pd.DataFrame(final_products)
    df['full_text'] = df['Product Name'].astype(str) + " - " + df['Description'].astype(str)

    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-large",  # or "text-embedding-3-small"
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

    # Step 3: Embed full_text and query
    product_embeddings = embeddings.embed_documents(df['full_text'].tolist())
    query_embedding = embeddings.embed_query(query)
    # for batch in chunked(df['full_text'].tolist(), 100):
    #     product_embeddings += embeddings.embed_documents(batch)
    #     query_embedding = embeddings.embed_query(query)

    # Step 4: Compute similarity
    similarities = cosine_similarity([query_embedding], product_embeddings)[0]
    df['similarity'] = similarities

    # Step 5: Sort and get top_k
    top_results = df.sort_values(by='similarity', ascending=False).head(top_k)

    # Step 6: Format output
    output = []
    for _, row in top_results.iterrows():
        variant_prices = ', '.join([v['Price'] for v in row['Variants'] if v.get('Price')])
        output.append(
            f"Product Name: {row['Product Name']}\n"
            f"Description: {row['Description']}\n"
            f"Price: ₹{variant_prices or 'N/A'}\n"
            f"Image: {row['Image']}\n"
            f"Link: {row['URL']}\n"
            f"Similarity Score: {row['similarity']:.2f}\n"
        )

    return "\n---\n".join(output)


def extract_products_from_edges(data):
    """
    Get the shopify products inside edges in graphql response of fetch_all_products
    """
    # If already a list of edges
    if isinstance(data, list):
        edges = data
    elif isinstance(data, dict) and 'edges' in data:
        edges = data['edges']
    else:
        raise ValueError("Input must be a dict with 'edges' or a list of edges.")

    products = []
    for edge in edges:
        node = edge.get('node', {}) if 'node' in edge else edge  # Safe fallback

        product = {
            'id': node.get('id'),
            'title': node.get('title'),
            'vendor': node.get('vendor'),
            'description': node.get('description'),
            'handle': node.get('handle'),
            'status': node.get('status'),
            'createdAt': node.get('createdAt'),
            'updatedAt': node.get('updatedAt'),
            'priceRange': node.get('priceRange', {}),
            'options': [
                {
                    'name': opt.get('name'),
                    'values': opt.get('values')
                }
                for opt in node.get('options', [])
            ],
            'variants': [
                {
                    'id': var['node'].get('id'),
                    'title': var['node'].get('title'),
                    'price': var['node'].get('price'),
                    'inventoryQuantity': var['node'].get('inventoryQuantity')
                }
                for var in node.get('variants', {}).get('edges', [])
            ],
            'images': [
                {'src': img['node'].get('src')}
                for img in node.get('images', {}).get('edges', [])
            ]
        }

        products.append(product)

    return products


def direct_upload_to_s3(file):
    """
    Uploads a file to AWS S3 in a predefined bucket and \
    generates a presigned URL for the uploaded file.

    """
    try:
        PIL_FORMAT_TO_MIME = {
            'JPEG': 'jpeg',
            'PNG': 'png',
            'GIF': 'gif',
        }
        random_id = "".join(
            random.choice(
                string.ascii_uppercase + string.ascii_lowercase + string.digits
            )
            for _ in range(5)
        )
        file_type = file.content_type
        file_name = file.name.replace(" ", "-").split(".")
        extension = file_name[-1].lower()

        logger.debug(f"File content type: {file_type}")

        if 'image' in file_type:
            raw_bytes = file.read()
            file_stream = io.BytesIO(raw_bytes)

            # Use PIL to detect the true format
            img = Image.open(file_stream)
            img_format = img.format.upper()
            if img_format not in PIL_FORMAT_TO_MIME:
                raise ValueError(f"Unsupported image format: {img_format}")

            mime_subtype = PIL_FORMAT_TO_MIME[img_format]
            file_type = f'image/{mime_subtype}'
            extension = 'jpg' if mime_subtype == 'jpeg' else mime_subtype
            file_body_to_upload = raw_bytes
        else:
            file_body_to_upload = file.read()

        timestamp = datetime.now().timestamp()
        unique_file_name = f"{file_name[0]}_{random_id}_{timestamp}.{extension}"

        logger.info(
            f"Original file name: {file_name[0]}, File extension: {extension}, Unique file name: {unique_file_name} .. {file_type}"
        )

        s3 = boto3.resource(
            "s3",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )

        # Upload the file
        object = s3.Object(
            os.getenv("AWS_STORAGE_BUCKET_NAME"),
            f"media/client_media/{unique_file_name}",
        )
        object.put(Body=file_body_to_upload, ContentType=file_type)
        final_path = f"{os.getenv('S3_BUCKET_URL')}/media/client_media/{unique_file_name}"
        logger.info(f"File uploaded successfully. Accessible aassett: {final_path}")

        return final_path
    
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"An error occurred during S3 upload: {e}")
        return None



@shared_task(queue='webhook_analytics')
def store_webhook_analytics(email, query, response_data, namespace, room_id):
    """
    Celery task to store webhook analytics by calling ConversationLogWebhookView API
    """
    try:
        analytics_url = f"https://staging.chat360.io/api/genai/store-angentic-analytics"
        
        payload = {
            'email': email,
            'query': query,
            'response': response_data, 
            'namespace': namespace,
            'room_id': room_id
        }
        
        logger.info(f"Storing analytics for room_id: {room_id} with payload: {payload}")
        
        http_response = requests.post(
            analytics_url,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if http_response.status_code == 202:
            logger.info(f"Analytics stored successfully for room_id: {room_id}")
        else:
            logger.error(f"Analytics API returned status {http_response.status_code} for room_id: {room_id}")
            logger.error(f"Response text: {http_response.text}")
            
    except Exception as e:
        logger.error(f"Error storing analytics for room_id {room_id}: {str(e)}")
        
        raise

import io
import pandas as pd
from datetime import datetime
from django.core.files.base import ContentFile
import logging


def export_all_rooms_data_to_excel():
    """
    Export ONLY ChatRoom.captured_data into an Excel file,
    upload to S3, and return the download link.
    """
    try:
        rooms = ChatRoom.objects.all().values("captured_data")

        if not rooms:
            logger.error("No ChatRoom records found in DB")
            return {"status": "error", "message": "No ChatRoom data found"}

        data = []
        for room in rooms:
            if room["captured_data"]:
                data.append(room["captured_data"])

        if not data:
            logger.error("No captured_data found in any ChatRoom")
            return {"status": "error", "message": "No captured data found"}

        df = pd.DataFrame(data)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="ChatRooms", index=False)
        output.seek(0)

       
        file_obj = ContentFile(output.read())
        file_obj.name = f"chatrooms_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        
        file_obj.content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

       
        s3_url = direct_upload_to_s3(file_obj)
        if not s3_url:
            logger.error("S3 upload failed — direct_upload_to_s3 returned None/Null")
            return {"status": "error", "message": "Upload to S3 failed"}

        return {"status": 200, "download_url": s3_url}

    except Exception as e:
        logger.error(f"Unexpected error during export: {str(e)}", exc_info=True)
        return {"status": "error", "message": str(e)}