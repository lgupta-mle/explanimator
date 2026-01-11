#!/usr/bin/env python
"""Inspect Pydantic schema structure and OpenAI compatibility."""

from research_viz.schemas.animation_schemas import SegmentAnimationPlan
from research_viz.utils.llm_utils import make_schema_openai_compatible
import json
import sys

def print_schema_info():
    # Get schemas
    raw_schema = SegmentAnimationPlan.model_json_schema()

    print(json.dumps(raw_schema, indent=2))
    # clean_schema = make_schema_openai_compatible(raw_schema)
    # print("="*100)
    # print(json.dumps(clean_schema, indent=2))

if __name__ == "__main__":
    print_schema_info()
