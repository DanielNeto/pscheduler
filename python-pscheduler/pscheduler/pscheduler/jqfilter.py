"""
JQ JSON Filter Class
"""

import pyjq

from .psjson import *

class JQFilter(object):
    """
    JQ JSON filter
    """

    def __init__(
            self,
            filter_spec=".",
            vars={},
            output_raw=False
            ):

        if isinstance(filter_spec, basestring):
            self.script = pyjq.compile(filter_spec, vars)
            self.output_raw = output_raw

        elif type(filter_spec) == dict:
            self.script = pyjq.compile(filter_spec.get("script", "."), vars)
            self.output_raw = filter_spec.get("output-raw", output_raw)

        else:
            raise ValueError("Filter spec must be plain text or dict")


    def __call__(
            self,
            json={}
    ):
        """
        Filter 'json' according to the script.  If output_raw is True,
        join everything that comes out of the filter into a a single
        string and return that.
        """

        result = self.script.all(json)

        if isinstance(result, list) and self.output_raw:
            return "\n".join([str(item) for item in result])

        elif isinstance(result, dict) or isinstance(result, list):
            return result

        else:
            raise ValueError("No idea what to do with %s result", type(result))




if __name__ == "__main__":

    # TODO:  Write a few examples.

    filter = JQFilter(".")
    print filter('{ "foo": 123, "bar": 456 }')

    pass
