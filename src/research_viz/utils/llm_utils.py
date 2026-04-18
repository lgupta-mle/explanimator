import logging
from pathlib import Path
import base64
import os
from typing import Optional, Type, TypeVar, Union, List, Dict, Any
from pydantic import BaseModel

from research_viz.config.pipeline_config import get_config, get_provider

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def create_llm_response(
    prepared_usr_prompt: str,
    system_prompt: str,
    model_name: str,
    images_dir: str = None,
    schema: Optional[Type[T]] = None,
    images_metadata: Optional[List[Dict[str, Any]]] = None,
) -> Union[str, T, None]:
    """Creates a response from the LLM via the provider abstraction.

    Args:
        prepared_usr_prompt: User prompt content
        system_prompt: System prompt content
        model_name: Required. Model identifier (e.g., "openai/gpt-5")
        schema: Optional Pydantic model for structured output
        images_metadata: Optional list of dicts with keys 'path', 'caption', 'figure_number'

    Returns:
        If schema is provided, returns instance of the schema type.
        Otherwise, returns the raw string response.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prepared_usr_prompt},
    ]

    # Add images to messages
    if images_metadata:
        for img_info in images_metadata:
            if not os.path.exists(img_info['path']):
                continue

            image_b64 = encode_image_to_base64(img_info['path'])
            caption = img_info.get('caption', '')
            figure_num = img_info.get('figure_number', '')

            content_parts = []
            if caption:
                caption_text = f"Figure {figure_num}: {caption}" if figure_num else f"Figure: {caption}"
                content_parts.append({"type": "text", "text": caption_text})

            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}",
                    "detail": "high",
                },
            })
            messages.append({"role": "user", "content": content_parts})
    elif images_dir:
        image_paths = sorted(Path(images_dir).glob("*.png"))
        for img_path in image_paths:
            image_b64 = encode_image_to_base64(str(img_path))
            messages.append({
                "role": "user",
                "content": [{
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}",
                        "detail": "high",
                    },
                }],
            })

    # Build kwargs for provider
    kwargs: dict = {}
    if schema is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": False,
            },
        }

    try:
        llm_response = get_provider().generate(messages, model_name, **kwargs)
    except Exception as e:
        logger.error(f"Error calling the LLM: {e}")
        return None

    content = llm_response.content

    if schema is not None:
        try:
            return schema.model_validate_json(content)
        except Exception as e:
            logger.error(f"Error parsing structured output: {e}")
            return None

    return content
