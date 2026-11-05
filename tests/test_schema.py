"""Tests for API JSON Schema validation against contracts/api_v1_schema.json."""
import json
import os
import jsonschema


def test_demo_fixture_validates_against_schema():
    """Verify demo_piano_analysis.json conforms to contracts/api_v1_schema.json."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    schema_path = os.path.join(base_dir, "contracts", "api_v1_schema.json")
    fixture_path = os.path.join(base_dir, "fixtures", "demo_piano_analysis.json")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    with open(fixture_path, "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    # Validate without error
    jsonschema.validate(instance=fixture_data, schema=schema)
