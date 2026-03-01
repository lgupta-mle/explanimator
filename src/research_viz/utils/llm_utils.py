import requests
from openai import OpenAI
from pathlib import Path
import base64
import json
import os
import copy
from typing import Optional, Type, TypeVar, Union, List, Dict, Any
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def call_openrouter(
    messages: list,
    model_name: str = "openai/gpt-5",
    schema: Optional[Type[T]] = None,
    plugins: Optional[list] = None
) -> dict:
    """Generic OpenRouter API call via requests."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model_name,
        "messages": messages
    }

    if plugins:
        payload["plugins"] = plugins

    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": False
            }
        }

    response = requests.post(url, headers=headers, json=payload)
    return response.json()


def make_schema_openai_compatible(schema: dict) -> dict:
    """
    Recursively process schema to make it compatible with OpenAI's strict mode.
    - Ensures ALL properties are in the 'required' array (including optional ones)
    - Sets additionalProperties to false for all objects
    - Removes additional keywords from $ref fields (OpenAI doesn't allow $ref with other keywords)
    - Strips title, description, default from all fields (OpenAI strict mode only wants core schema)

    Note: OpenAI's strict mode requires all fields to be in the required array,
    even Optional fields. Optional fields use type: [type, "null"] pattern.

    Root cause: Pydantic includes Field descriptions, titles, and defaults in generated schemas,
    which is valid JSON Schema but incompatible with OpenAI's stricter requirements.
    """

    if isinstance(schema, dict):
        # If this dict has a $ref, strip all other keys (OpenAI doesn't allow $ref with other keywords)
        if "$ref" in schema:
            return {"$ref": schema["$ref"]}

        # Remove fields that OpenAI strict mode doesn't allow
        keys_to_remove = ["title", "description", "default"]
        for key in keys_to_remove:
            schema.pop(key, None)

        # Process nested objects first
        for key, value in schema.items():
            if isinstance(value, (dict, list)):
                schema[key] = make_schema_openai_compatible(value)

        # If this object has properties, make ALL of them required
        if "properties" in schema:
            # Include all properties in required array
            schema["required"] = list(schema["properties"].keys())

            # Ensure additionalProperties is false
            if "additionalProperties" not in schema:
                schema["additionalProperties"] = False

        # Process $defs (Pydantic v2 uses $defs instead of definitions)
        if "$defs" in schema:
            for def_name in schema["$defs"]:
                schema["$defs"][def_name] = make_schema_openai_compatible(schema["$defs"][def_name])

    elif isinstance(schema, list):
        return [make_schema_openai_compatible(item) for item in schema]

    return schema

def create_llm_response(
    prepared_usr_prompt: str,
    system_prompt: str,
    images_dir: str = None,
    model_name: str = "openai/gpt-5",
    schema: Optional[Type[T]] = None,
    images_metadata: Optional[List[Dict[str, Any]]] = None
) -> Union[str, T]:
    """
    Creates a response from the LLM.

    Args:
        prepared_usr_prompt: User prompt content
        system_prompt: System prompt content
        images_dir: Directory containing images (legacy, used if images_metadata not provided)
        model_name: Model identifier (e.g., "openai/gpt-5")
        schema: Optional Pydantic model for structured output
        images_metadata: Optional list of dicts with keys 'path', 'caption', 'figure_number'
                        If not provided, falls back to images_dir

    Returns:
        If schema is provided, returns instance of the schema type.
        Otherwise, returns the raw string response.
    """

    # Create the LLM client
    use_openrouter = True
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))

    # Prepare messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prepared_usr_prompt}
    ]

    # Add images to messages
    if images_metadata:
        # Use provided metadata with captions
        for img_info in images_metadata:
            if not os.path.exists(img_info['path']):
                continue

            image_b64 = encode_image_to_base64(img_info['path'])
            caption = img_info.get('caption', '')
            figure_num = img_info.get('figure_number', '')

            # Create multi-part content with caption and image
            content_parts = []

            # Add caption as text if available
            if caption:
                caption_text = f"Figure {figure_num}: {caption}" if figure_num else f"Figure: {caption}"
                content_parts.append({
                    "type": "text",
                    "text": caption_text
                })

            # Add the image
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}",
                    "detail": "high"
                }
            })

            messages.append({
                "role": "user",
                "content": content_parts
            })
    elif images_dir:
        # Read all images from directory without captions
        image_paths = sorted(Path(images_dir).glob("*.png"))
        for img_path in image_paths:
            image_b64 = encode_image_to_base64(str(img_path))
            messages.append({
                "role": "user",
                "content": [{
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}",
                        "detail": "high"
                    }
                }]
            })

    # Prepare API call parameters
    api_params = {
        "model": model_name if use_openrouter else model_name.split("/")[1],
        "messages": messages
    }

    # Add structured output if schema provided
    if schema is not None:
        json_schema = schema.model_json_schema()
        # Make schema compatible with OpenAI's strict mode
        # json_schema = make_schema_openai_compatible(json_schema)
        api_params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": json_schema,
                "strict": False
            }
        }

    # Call the LLM
    try:
        response = client.chat.completions.create(**api_params)
    except Exception as e:
        print(f"Error calling the LLM: {e}")
        return None

    content = response.choices[0].message.content
    print("Usage: ", response.usage)

    # Parse and validate if schema provided
    if schema is not None:
        try:
            return schema.model_validate_json(content)
        except Exception as e:
            print(f"Error parsing structured output: {e}")
            print(f"Raw response: {content}")
            return None

    return content