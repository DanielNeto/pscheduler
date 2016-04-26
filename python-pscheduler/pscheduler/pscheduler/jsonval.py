"""
Functions for validating JSON against the pScheduler JSON and standard
values dictionaries
"""

import jsonschema


#
# Types from the dictionary
#
__dictionary__ = {
    
    #
    # JSON Types
    #

    "AnyJSON": {
        "oneOf": [
            { "type": "array" },
            { "type": "boolean" },
            { "type": "integer" },
            { "type": "null" },
            { "type": "number" },
            { "type": "object" },
            { "type": "string" }
            ]
        },

    "Array": { "type": "array" },

    "Boolean": { "type": "boolean" },

    "Cardinal": {
        "type": "integer",
        "minimum": 1,
        },

    "CardinalZero": {
        "type": "integer",
        "minimum": 0,
        },

    "Duration": {
        "type": "string",
        # ISO 8601.  Source: https://gist.github.com/philipashlock/8830168
        "pattern": r'^(R\d*\/)?P(?:\d+(?:\.\d+)?Y)?(?:\d+(?:\.\d+)?M)?(?:\d+(?:\.\d+)?W)?(?:\d+(?:\.\d+)?D)?(?:T(?:\d+(?:\.\d+)?H)?(?:\d+(?:\.\d+)?M)?(?:\d+(?:\.\d+)?S)?)?$'
        },

    "Email": { "type": "string", "format": "email" },

    "GeneralNumber": {
        # TODO: This doesn't exist in the doc.
        "anyOf": [
            { "type": "number" },
            {
                # Binary number (Decimal, octal, hex or binary)
                "type": "string",
                # Source: https://www.safaribooksonline.com/library/view/regular-expressions-cookbook/9781449327453/ch07s03.html
                "pattern": "^(?:([1-9][0-9]*)|(0[0-7]*)|0x([0-9A-Fa-f]+)|0b([01]+))$"
                },

            { "$ref": "#/pScheduler/si-number" },
            ]
        },

    "GeographicPosition": {
        "type": "string",
        # ISO 6709
        # Source:  https://svn.apache.org/repos/asf/abdera/abdera2/common/src/main/java/org/apache/abdera2/common/geo/IsoPosition.java
        "pattern": r'^(([+-]\d{2})(\d{2})?(\d{2})?(\.\d+)?)(([+-]\d{3})(\d{2})?(\d{2})?(\.\d+)?)([+-]\d+(\.\d+)?)?$'
        },

    "Host": {
        "type": "string",
        "format": "host-name"
        },

    "Integer": { "type": "integer" },

    # TODO: This needs to go into the dict doc
    "IPAddress": {
        "oneOf": [
            { "type": "string", "format": "ipv4" },
            { "type": "string", "format": "ipv6" },
            ]
        },

    "IPPort": {
        "type": "integer",
        "minimum": 0,
        "maximum": 65535
        },

    "Number": { "type": "number" },

    "Probability": {
        "type": "number",
        "minimum": 0.0,
        "maximum": 1.0
        },

    "SINumber":  {
        "type": "string",
        "pattern": r'^[0-9]+(\.[0-9]+)?([KkMmGgTtPpEeZzYy][Ii]?)?$'
        },

    "String": { "type": "string" },

    "Timestamp": {
        "type": "string",
        # ISO 8601.  Source: https://gist.github.com/philipashlock/8830168
        "pattern": r'^([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3([12]\d|0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-9]|0[1-9]\d|[12]\d{2}|3([0-5]\d|6[1-6])))([T\s]((([01]\d|2[0-3])((:?)[0-5]\d)?|24\:?00)([\.,]\d+(?!:))?)?(\17[0-5]\d([\.,]\d+)?)?([zZ]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?)?)?$'
        },

    "TimestampAbsoluteRelative": {
        "oneOf" : [
            { "$ref": "#/pScheduler/Timestamp" },
            { "$ref": "#/pScheduler/Duration" },
            {
                "type": "string",
                # Same pattern as iso8601-duration, with '@' prepended
                "pattern": r'^@(R\d*/)?P(?:\d+(?:\.\d+)?Y)?(?:\d+(?:\.\d+)?M)?(?:\d+(?:\.\d+)?W)?(?:\d+(?:\.\d+)?D)?(?:T(?:\d+(?:\.\d+)?H)?(?:\d+(?:\.\d+)?M)?(?:\d+(?:\.\d+)?S)?)?$'
                }
            ]
        },

    "URL": { "type": "string", "format": "uri" },

    "UUID": {
        "type": "string",
        # TODO: POSIX xdigit doesn't seem to work here.
        "pattern": r'^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$'
        },

    "Version": {
        "type": "string",
        "pattern": r'^[0-9]+(\.[0-9]+(\.[0-9]+)?)$'
        },


    #
    # Standard Values
    #

    # TODO: Put this into the documentation
    "icmp-error": {
        "type": "string",
        "enum": [
            'net-unreachable',
            'host-unreachable',
            'protocol-unreachable',
            'port-unreachable',
            'fragmentation-needed-and-df-set',
            'source-route-failed',
            'destination-network-unknown',
            'destination-host-unknown',
            'source-host-isolated',
            'destination-network-administratively-prohibited',
            'destination-host-administratively-prohibited',
            'network-unreachable-for-type-of-service',
            'icmp-destination-host-unreachable-tos',
            'communication-administratively-prohibited',
            'host-precedence-violation',
            'precedence-cutoff-in-effect',
            ]
        },

    "ip-version": {
        "type": "integer",
        "enum": [ 4, 6 ]
        }


    #
    # Compound Types
    #

    # TODO: ArchiveSpecification (Compound)
    # TODO: Maintainer (Compound)
    # TODO: NameVersion (Compound)
    # TODO: ParticipantResult (Compound)
    # TODO: RunResult (Compound)
    # TODO: ScheduleSpecification (Compound)
    # TODO: TaskSpecification (Compound)
    # TODO: TestSpecification (Compound)
    # TODO: TimeInterval (Compound) -- Is this being used anywhere?
    # TODO: TimeRange (Compound) -- Is this being used anywhere?


    }


__default_schema__ = {

    # TODO: Find out if this is downloaded or just a placeholder
    "$schema": "http://json-schema.org/draft-04/schema#",
    "id": "http://perfsonar.net/pScheduler/json_generic.json",
    "title": "pScheduler Generic Validation Schema",

    "type": "object",
    "additionalProperties": False,

    "pScheduler": __dictionary__
}




def json_validate(json, skeleton):
    """
    Validate JSON against a jsonschema schema.

    The skeleton is a dictionary containing a partial,
    draft-04-compatible jsonschema schema, containing only the
    following:

        type         (array, boolean, integer, null, number, object, string)
        items        (Only when type is array)
        properties   (Only when type is object)
        required     Required items
        local        (Optional; see below.)

    The optional 'local' element is a dictionary which may be used for
    any local definitions to be referenced from the items or
    properties sections.

    The standard pScheduler types are available for reference as
    "#/pScheduler/TypeName", where TypeName is a standard pScheduler
    type as defined in the "pScheduler JSON Style Guide and Type
    Dictionary" document."

    The values returned are a tuple containing a boolean indicating
    whether or not the JSON was valid and a string containing any
    error messages if not.
    """

    # Validate what came in

    if type(json) != dict:
        raise ValueError("JSON provided must be a dictionary.")

    if type(skeleton) != dict:
        raise ValueError("Skeleton provided must be a dictionary.")


    # Build up the schema from the dictionaries and user input.

    schema = __default_schema__
    for element in [ 'type', 'items', 'properties', 'required', 'local' ]:
        if element in skeleton:
            schema[element] = skeleton[element]

    # Let this throw whatever it's going to throw, since schema errors
    # are problems wih the software, not the data.
    jsonschema.Draft4Validator.check_schema(schema)

    jsonschema.Draft4Validator.check_schema(schema)

    try:
        jsonschema.validate(json, schema,
                            format_checker=jsonschema.FormatChecker())
    except jsonschema.exceptions.ValidationError as ex:
        # TODO: Need something human-readable here.
        return (False, str(ex))


    return (True, 'OK')


# Test program

if __name__ == "__main__":

    sample = {
        "schema": 1,
        "when": "2015-06-12T13:48:19.234",
        "howlong": "PT10M",
        "sendto": "bob@example.com",
        "x-factor": 3.14,
        "protocol": "udp",
        "ipv": 6,
        "ip": "fc80:dead:beef::"
        }

    schema = {
        "local": {
            "protocol": {
                "type": "string",
                "enum": ['icmp', 'udp', 'tcp']
                }
            },
        "type": "object",
        "properties": {
            "schema":   { "$ref": "#/pScheduler/Cardinal" },
            "when":     { "$ref": "#/pScheduler/Timestamp" },
            "howlong":  { "$ref": "#/pScheduler/Duration" },
            "sendto":   { "$ref": "#/pScheduler/Email" },
            "ipv":      { "$ref": "#/pScheduler/ip-version" },
            "ip":       { "$ref": "#/pScheduler/IPAddress" },
            "protocol": { "$ref": "#/local/protocol" },
            "x-factor": { "type": "number" },

            },
        "required": [ "sendto", "x-factor" ]
        }

    valid, message = json_validate(sample, schema)

    print valid, message

