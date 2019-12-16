# -*- coding: utf-8 -*-
import logging

from collections import OrderedDict

import click

from html_checker.cli.common import COMMON_OPTIONS
from html_checker.exceptions import (HtmlCheckerUnexpectedException,
                                     HtmlCheckerBaseException)
from html_checker.export import LogExportBase
from html_checker.validator import ValidatorInterface


@click.command()
@click.option(*COMMON_OPTIONS["xss"]["args"],
              **COMMON_OPTIONS["xss"]["kwargs"])
@click.option(*COMMON_OPTIONS["no-stream"]["args"],
              **COMMON_OPTIONS["no-stream"]["kwargs"])
@click.option(*COMMON_OPTIONS["user-agent"]["args"],
              **COMMON_OPTIONS["user-agent"]["kwargs"])
@click.option(*COMMON_OPTIONS["safe"]["args"],
              **COMMON_OPTIONS["safe"]["kwargs"])
@click.option(*COMMON_OPTIONS["split"]["args"],
              **COMMON_OPTIONS["split"]["kwargs"])
@click.argument('paths', nargs=-1, required=True)
@click.pass_context
def page_command(context, xss, no_stream, user_agent, safe, split, paths):
    """
    Validate pages from given paths.

    Path can be an url starting with 'http://' or 'https://' or a file path.

    You can give many paths to validate each one.
    """
    logger = logging.getLogger("py-html-checker")

    logger.debug("Launching validation for {} paths".format(len(paths)))

    print()
    print("CLI page: safe:", safe)

    # Safe mode enabled, catch all internal exceptions
    if safe:
        CatchedException = HtmlCheckerBaseException
    # Safe mode disabled, watch for a dummy exception that won't never occurs
    # so internal exception are still raised
    else:
        CatchedException = HtmlCheckerUnexpectedException

    # Compile options
    interpreter_options = OrderedDict([])
    tool_options = OrderedDict([])

    if no_stream:
        tool_options["--no-stream"] = None

    if user_agent:
        tool_options["--user-agent"] = user_agent

    if xss:
        key = "-Xss{}".format(xss)
        interpreter_options[key] = None

    v = ValidatorInterface(exception_class=CatchedException)
    exporter = LogExportBase()

    # Get report from validator process
    try:
        report = v.validate(paths, interpreter_options=interpreter_options,
                            tool_options=tool_options, split=split)
        logger.debug(report)
        exporter.build(report)
    except CatchedException as e:
        # TODO: may be broken, would need to introduce a top level fake bug
        # like wrong validator tool path and so can tests to implement critical
        # top level error
        print("🔥 CLI page catched exception")
        exporter.build({
            "all": [{
                "type": "critical",
                "message": e,
            }]
        })
    else:
        print("🔥 CLI page no exception catched")

    exporter.release()
