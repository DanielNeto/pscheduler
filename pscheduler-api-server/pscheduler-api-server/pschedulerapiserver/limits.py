#
# Limit-Related Pages
#

import pscheduler

from pschedulerapiserver import application

from flask import request

from .args import *
from .limitproc import *
from .response import *

@application.route("/limits", methods=['GET'])
def limits():

    try:
        proposal = arg_json('proposal')
    except ValueError as ex:
        return bad_request(str(ex))

    if proposal is None:
        return bad_request("No proposal provided")

    hints = {
        "ip": request.remote_addr
        }

    processor = limitprocessor()
    if processor is None:
        return no_can_do("Limit processor is not initialized.")

    passed, diags = processor.process(proposal, hints)

    return json_response({
            "passed": passed,
            "diags": diags
            })

