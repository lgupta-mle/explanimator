from openai import OpenAI
from pathlib import Path
import base64
import json
import os
from typing import Optional, Type, TypeVar, Union, List, Dict, Any
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

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
    if model_name.startswith("openai/"):
        client = OpenAI()
    else:
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
        "model": model_name,
        "messages": messages
    }

    # Add structured output if schema provided
    if schema is not None:
        json_schema = schema.model_json_schema()
        api_params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": json_schema,
                "strict": True
            }
        }

    # Call the LLM
    try:
        response = client.chat.completions.create(**api_params)
    except Exception as e:
        print(f"Error calling the LLM: {e}")
        return None

    content = response.choices[0].message.content

    # Parse and validate if schema provided
    if schema is not None:
        try:
            return schema.model_validate_json(content)
        except Exception as e:
            print(f"Error parsing structured output: {e}")
            print(f"Raw response: {content}")
            return None

    return content