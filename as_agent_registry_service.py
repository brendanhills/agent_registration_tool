import subprocess
import json
import logging
import google.auth
import google.auth.transport.requests

logger = logging.getLogger(__name__)
logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.INFO)

# Scopes define the level of access you are requesting.
# For this example, we are using the default cloud-platform scope.
# You may need to specify more granular scopes depending on your needs.
SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

def get_access_token():
    """Gets the access token from the environment."""
    try:
        # google.auth.default() automatically finds the credentials
        # from the environment (e.g., a service account key).
        credentials, project_id = google.auth.default(scopes=SCOPES)

        # Refresh the credentials to get an access token.
        # Provide a transport object for refreshing.
        credentials.refresh(google.auth.transport.requests.Request())

        return credentials.token
    except Exception as e:
        logging.error(f"An error occurred in get_access_token: {e}")
        #print(f"An error occurred in get_access_token: {e}")
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            import traceback
            traceback.print_exc() # This will print the full stack trace
        return None


# --- Constants for URL construction ---
BASE_API_URL = "https://{location_prefix}discoveryengine.googleapis.com/v1alpha"
DEFAULT_LOCATION = "global"
DEFAULT_COLLECTION = "default_collection"
DEFAULT_ASSISTANT = "default_assistant"

def _check_required_params(params, required):
    missing = [param for param in required if not params.get(param)]
    if missing:
        raise ValueError(f"Missing required parameters: {', '.join(missing)}")

def _build_discovery_engine_url(project_id: str, app_id: str, agent_id: str = None, api_location: str = DEFAULT_LOCATION) -> str:
    """Helper function to construct the Discovery Engine API URL for agents."""
    location_prefix = ""
    if api_location != "global":
        location_prefix = api_location + "-"
    url = BASE_API_URL.format(location_prefix=location_prefix)
    base_path = f"{url}/projects/{project_id}/locations/{api_location}/collections/{DEFAULT_COLLECTION}/engines/{app_id}/assistants/{DEFAULT_ASSISTANT}/agents"
    if agent_id:
        return f"{base_path}/{agent_id}"
    return base_path

def create_agent(project_id, app_id, display_name, description, tool_description, adk_deployment_id, auth_id, icon_uri=None, re_location="global", api_location="global", re_resource_name=None):
    """
    Creates a new agent in the Agent Registry.

    Args:
        project_id (str): Google Cloud Project ID.
        app_id (str): App ID for the Discovery Engine.
        display_name (str): Display name of the agent.
        description (str): Description of the agent.
        tool_description (str): Tool description for the agent.
        adk_deployment_id (str): Reasoning Engine ID.
        auth_id (str): Authorization ID.
        icon_uri (str, optional): Icon URI for the agent. Defaults to None.
        re_location (str, optional): Location of the Reasoning Engine and Authorizations. Defaults to "global".
        api_location (str, optional): API location for the Discovery Engine service. Defaults to "global".

    Returns:
        dict: A dictionary containing the status code, stdout, and stderr of the curl command.
    """
  
    
    _check_required_params(locals(), ["project_id", "app_id", "display_name", "description", "tool_description", "adk_deployment_id"])
    access_token = get_access_token()
    if not access_token:
        logging.error("Failed to obtain access token for create_agent.")
        return {
            "status_code": 401, # Unauthorized
            "stdout": "",
            "stderr": "Failed to obtain access token.",
            "error": "Authentication failed: Could not retrieve access token."
        }

    url = _build_discovery_engine_url(project_id, app_id, api_location=api_location)

    #construct the reasoning engine resource name if it wasn't passed in
    if not re_resource_name:
        re_resource_name = f"projects/{project_id}/locations/{re_location}/reasoningEngines/{adk_deployment_id}"
    
    # Prepare the request body
    data = {
        "displayName": display_name,
        "description": description,
        "adk_agent_definition": {
            "tool_settings": {
                "tool_description": tool_description
            },
            "provisioned_reasoning_engine": {
                "reasoning_engine": re_resource_name
            },
            "authorizations": [f"projects/{project_id}/locations/{api_location}/authorizations/{auth_id}"] if auth_id else [],
        }

    }

    if icon_uri:
        data["icon"] = {"uri": icon_uri}

    # Prepare the curl command
    command = [
        "curl", "-X", "POST",
        "-H", f"Authorization: Bearer {access_token}",
        "-H", "Content-Type: application/json",
        "-H", f"X-Goog-User-Project: {project_id}",
        url,
        "-d", json.dumps(data)
    ]

    logging.debug(f"Create Agent Command: {command}")

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0 and "error" not in result.stdout.lower():
        try:
            agent_data = json.loads(result.stdout)
            agent_name = agent_data.get("name")
            logging.debug(f"Create Agent Response: {agent_data}")
            return {"status_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "agent": agent_data, "message": "Agent created successfully: " + agent_name }
        except json.JSONDecodeError:
            return {"status_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "message": "Could not decode JSON response."}
    else:
        error_message = json.loads(result.stdout).get("error", {}).get("message", result.stdout)
        error_code = json.loads(result.stdout).get("error", {}).get("code", "Unknown code")
        logging.error(f"Create Agent Error: {error_code}, {error_message}")
        logging.debug(f"Create Agent Response: {result.stdout}")
    return {"status_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "message": "Agent registration failed: " + error_message}


def list_agents(project_id, app_id, api_location="global"):
    """
    Lists agents in the Agent Registry for a given project and app.

    Args:
        project_id (str): Google Cloud Project ID.
        app_id (str): App ID for the Discovery Engine.
        api_location (str, optional): API location for the Discovery Engine service. Defaults to "global".

    Returns:
        dict: A dictionary containing a list of agents or an error message.
    """
    _check_required_params(locals(), ["project_id", "app_id"])

    access_token=get_access_token()
    if not access_token:
        logging.error(f"Failed to obtain access token for list_agents (project_id: {project_id}, app_id: {app_id}).")
        return {
            "status_code": 401, # Unauthorized
            "stdout": "",
            "stderr": "Failed to obtain access token.",
            "error": "Authentication failed: Could not retrieve access token."
        }


    url = _build_discovery_engine_url(project_id, app_id, api_location=api_location)

    # Prepare the curl command
    command = [
        "curl", "-X", "GET",
        "-H", f"Authorization: Bearer {access_token}",
        "-H", "Content-Type: application/json",
        "-H", f"X-Goog-User-Project: {project_id}",
        url
    ]

    logging.debug(f"List Agents Command: {command}")
    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Return the output as a list of agents
    if result.returncode == 0:
        try:
            agents_data = json.loads(result.stdout)
            logging.debug(f"List Agents Response: {agents_data}")
            if "agents" in agents_data:
                return {"agents": agents_data["agents"]}
            else:
                return {"agents": []}
        except json.JSONDecodeError:
            return {"error": "Could not decode JSON response.", "stderr": result.stderr}
    else:
        return {"error": "Error during agent listing", "stderr": result.stderr}

def get_agent(project_id, app_id, agent_id, api_location="global"):
    """
    Retrieves details for a specific agent from the Agent Registry.

    Args:
        project_id (str): Google Cloud Project ID.
        app_id (str): App ID for the Discovery Engine.
        agent_id (str): ID of the agent to retrieve.
        api_location (str, optional): API location for the Discovery Engine service. Defaults to "global".

    Returns:
        dict: A dictionary containing the agent details or an error message.
    """
    _check_required_params(locals(), ["project_id", "app_id", "agent_id"])

    access_token=get_access_token()
    if not access_token:
        logging.error(f"Failed to obtain access token for get_agent (project_id: {project_id}, app_id: {app_id}, agent_id: {agent_id}).")
        return {
            "status_code": 401, # Unauthorized
            "stdout": "",
            "stderr": "Failed to obtain access token.",
            "error": "Authentication failed: Could not retrieve access token."
        }

    
    url = _build_discovery_engine_url(project_id, app_id, agent_id, api_location=api_location)

    # Prepare the curl command
    command = [
        "curl", "-X", "GET",
        "-H", f"Authorization: Bearer {access_token}",
        "-H", "Content-Type: application/json",
        "-H", f"X-Goog-User-Project: {project_id}",
        url
    ]

    logging.debug(f"Get Agent Command: {command}")
    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0:
        try:
            agent_data = json.loads(result.stdout)
            logging.debug(f"Get Agent Response: {agent_data}")
            return {"agent_details": agent_data}
        except json.JSONDecodeError:
            return {"error": "Could not decode JSON response.", "stderr": result.stderr}
    else:
        return {"error": f"Error: {result.returncode} - {result.stderr}"}


def update_agent(project_id, app_id, agent_id, display_name, description, tool_description, adk_deployment_id, auth_id, icon_uri=None, re_location="global", api_location="global"):
    """
    Updates an existing agent in the Agent Registry.

    Args:
        project_id (str): Google Cloud Project ID.
        app_id (str): App ID for the Discovery Engine.
        agent_id (str): ID of the agent to update.
        display_name (str): New display name for the agent (leave blank to keep current).
        description (str): New description for the agent (leave blank to keep current).
        tool_description (str): New tool description (leave blank to keep current).
        adk_deployment_id (str): New Reasoning Engine ID (leave blank to keep current).
        auth_id (str, optional): New Authorization ID (leave blank to keep current). Defaults to None.
        icon_uri (str, optional): New icon URI (leave blank to keep current). Defaults to None.
        re_location (str, optional): Location of the Reasoning Engine and Authorizations if they are being updated. Defaults to "global".
        api_location (str, optional): API location for the Discovery Engine service. Defaults to "global".
    
    Returns:    
        dict: A dictionary containing the status code, stdout, stderr, and optionally the updated agent details or an error message.
    """
    _check_required_params(locals(), ["project_id", "app_id", "agent_id"]) # Check primary IDs first

    # First get the agent
    get_result = get_agent(project_id, app_id, agent_id, api_location=api_location)
    if "agent_details" not in get_result:
        return {"error": f"Could not retrieve agent details: {get_result.get('error', '')}"}
    
    existing_agent = get_result["agent_details"]

    # Prepare updated data. Use existing values as defaults.
    updated_data = {
        "displayName": display_name or existing_agent.get("displayName", ""),
        "description": description or existing_agent.get("description", ""),
    }

    #Handle adk_agent_definition.
    existing_adk = existing_agent.get("adkAgentDefinition", {})
    updated_adk = {}

    #Tool settings
    existing_tool = existing_adk.get("toolSettings", {})
    updated_adk["tool_settings"] = {
        "tool_description": tool_description or existing_tool.get("toolDescription", "")
    }

    #Reasoning engine
    existing_reasoning_engine_info = existing_adk.get("provisionedReasoningEngine", {})
    if adk_deployment_id: # If a new ADK deployment ID is provided, update it with the new re_location
        updated_adk["provisionedReasoningEngine"] = {
            "reasoning_engine": f"projects/{project_id}/locations/{re_location}/reasoningEngines/{adk_deployment_id}"
        }
    elif existing_reasoning_engine_info: # Otherwise, keep the existing one
        updated_adk["provisionedReasoningEngine"] = existing_reasoning_engine_info

    #Authorizations
    existing_auths = existing_adk.get("authorizations", [])
    if auth_id: # If a new auth ID is provided, update it with the new re_location
        updated_adk["authorizations"] = [f"projects/{project_id}/locations/{re_location}/authorizations/{auth_id}"]
    else: # Otherwise, keep the existing ones
        updated_adk["authorizations"] = existing_auths


    existing_icon = existing_agent.get("icon")
    if icon_uri:  # If new icon URI is provided
        updated_data["icon"] = {"uri": icon_uri}
    elif existing_icon:  # If no new URI, retain the existing icon
        updated_data["icon"] = existing_icon

    updated_data["adk_agent_definition"] = updated_adk

    url = _build_discovery_engine_url(project_id, app_id, agent_id, api_location=api_location)

    # Get access token
    #access_token = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip()
    access_token=get_access_token()
    if not access_token:
        logging.error(f"Failed to obtain access token for update_agent (project_id: {project_id}, app_id: {app_id}, agent_id: {agent_id}).")
        return {
            "status_code": 401, # Unauthorized
            "stdout": "",
            "stderr": "Failed to obtain access token.",
            "error": "Authentication failed: Could not retrieve access token."
        }



    # Prepare the curl command
    logging.debug(f"Updated Data: {json.dumps(updated_data, indent=2)}")
    command = [
        "curl", "-X", "PATCH",
        "-H", f"Authorization: Bearer {access_token}",
        "-H", "Content-Type: application/json",
        "-H", f"X-Goog-User-Project: {project_id}",
        url,
        "-d", json.dumps(updated_data, indent=2)
    ]

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    # Return results as JSON
    response = {"status_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    if result.returncode == 0:
        try:
            updated_agent = json.loads(result.stdout)
            response["updated_agent"] = updated_agent
        except json.JSONDecodeError:
            response["error"] = "Could not decode JSON response for updated agent."
    return response

def get_agent_by_display_name(project_id, app_id, display_name, api_location="global"):
    """
    Retrieves an agent from the Agent Registry by its display name.

    Args:
        project_id (str): Google Cloud Project ID.
        app_id (str): App ID for the Discovery Engine.
        display_name (str): Display name of the agent to retrieve.
        api_location (str, optional): API location for the Discovery Engine service. Defaults to "global".

    Returns:
        dict: A dictionary containing the agent details or a message indicating the agent was not found.
    """
    _check_required_params(locals(), ["project_id", "app_id", "display_name"])
    list_result = list_agents(project_id, app_id, api_location=api_location)
    if "error" in list_result:
        return list_result

    agents = list_result.get("agents", [])
    for agent in agents:
        if agent.get("displayName") == display_name:
            return {"agent": agent}

    return {"message": f"Agent with display name '{display_name}' not found."}


def delete_agent(project_id, app_id, agent_id, api_location="global"):
    """
    Deletes an agent from the Agent Registry.

    Args:
        project_id (str): Google Cloud Project ID.
        app_id (str): App ID for the Discovery Engine.
        agent_id (str): ID of the agent to delete.
        api_location (str, optional): API location for the Discovery Engine service. Defaults to "global".

    Returns:
        dict: A dictionary containing the status code, stdout, and stderr of the curl command,
              or an error message.
    """
    _check_required_params(locals(), ["project_id", "app_id", "agent_id"])

    #access_token = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip()
    access_token=get_access_token()
    if not access_token:
        logging.error(f"Failed to obtain access token for delete_agent (project_id: {project_id}, app_id: {app_id}, agent_id: {agent_id}).")
        return {
            "status_code": 401, # Unauthorized
            "stdout": "",
            "stderr": "Failed to obtain access token.",
            "error": "Authentication failed: Could not retrieve access token."
        }


    url = _build_discovery_engine_url(project_id, app_id, agent_id, api_location=api_location)

    # Prepare the curl command
    command = [
        "curl", "-X", "DELETE",
        # Although DELETE often doesn't need this, it's good practice
        "-H", f"Authorization: Bearer {access_token}",
        "-H", "Content-Type: application/json",  # Although DELETE often doesn't need this, it's good practice
        "-H", f"X-Goog-User-Project: {project_id}",
        url
    ]

    logging.debug(f"Delete Agent Command: {command}")

    # Execute the command
    result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode == 0 and "error" not in result.stdout.lower() :
        logger.info(f"Agent {agent_id} deleted successfully.")
        return {"status_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "message": f"Agent {agent_id} deleted successfully."}
    else:
        error_json = json.loads(result.stdout).get("error", {})
        if error_json == {}:
            logger.warning(f"Could not parse stdout as JSON: {result.stdout}")
        error_message = error_json.get("message", result.stdout)
        error_code = error_json.get("code", "Unknown code")
        logger.error(f"Error deleting agent {agent_id}: {result.returncode}, {error_code}, {error_message}")
    
        return {"status_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr, "message": f"Error deleting agent: {error_message}"}