#
# Validator for "simplestream" Test
#

from pscheduler import json_validate

def spec_is_valid(json):
    schema = {
        "type": "object",
        "properties": {
            "dawdle":         { "$ref": "#/pScheduler/Duration" },
            "fail":           { "$ref": "#/pScheduler/Probability" },
            "receiver":       { "$ref": "#/pScheduler/Host" },
            "schema":         { "$ref": "#/pScheduler/Cardinal" },
            "test-material":  { "$ref": "#/pScheduler/String" },
            "timeout":        { "$ref": "#/pScheduler/Duration" },
            },
        "required": [
            "receiver",
            "schema",
            ]
        }
    return json_validate(json, schema)


def result_is_valid(json):
    schema = {
        "type": "object",
        "properties": {
            "dawdled":       { "$ref": "#/pScheduler/Duration" },
            "elapsed-time":  { "$ref": "#/pScheduler/Duration" },
            "received":      { "$ref": "#/pScheduler/String" },
            "schema":        { "$ref": "#/pScheduler/Cardinal" },
            "sent":          { "$ref": "#/pScheduler/String" },
            "succeeded":     { "$ref": "#/pScheduler/Boolean" },
            },
        "required": [
            "dawdled",
            "elapsed-time",
            "received",
            "schema",
            "sent",
            "succeeded",
            ]
        }
    return json_validate(json, schema)
