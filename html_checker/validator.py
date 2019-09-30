import json
import logging
import os
import subprocess
from collections import OrderedDict


import html_checker
from html_checker.exceptions import ValidatorError
from html_checker.reporter import ReportStore
from html_checker.utils import reduce_unique


class ValidatorInterface:
    """
    Interface for validator tool

    Attributes:
        INTERPRETER (string): Leading interpreter name to execute tool.
        VALIDATOR (string): Path to validator tool to be executed by
            interpreter. It can contain leading ``{HTML_CHECKER}`` pattern to
            be replaced with absolute path to "py-html-checker" install.
        log (logging): Logging object set to application "py-html-checker".
    """
    REPORT_CLASS = ReportStore
    INTERPRETER = "java"
    VALIDATOR = "{HTML_CHECKER}/vnujar/vnu.jar"

    def __init__(self):
        self.log = logging.getLogger("py-html-checker")

    def compile_options(self, options):
        """
        Compile options to a list.

        Arguments:
            options (dict): A dict or a OrderedDict of options to
                compile to a list of arguments. Option values can be either a
                string or a list.

        Returns:
            list: List of options arguments.
        """
        opts = []

        for name, value in options.items():
            if name:
                opts.append(name)

            if value:
                if isinstance(value, list) or isinstance(value, tuple):
                    opts.extend(value)
                else:
                    opts.append(value)

        return opts

    def get_interpreter_part(self, options=None):
        """
        Return the command line interpreter part (its name then options).

        Keyword Arguments:
            options (list): List of interpreter arguments to include.

        Returns:
            list: List of items to build command line for interpreter (name
            and possible options).
        """
        args = []

        if self.INTERPRETER:
            args.append(self.INTERPRETER)

        if options:
            args.extend(self.compile_options(options))

        if self.INTERPRETER == "java":
            args.append("-jar")

        return args

    def get_validator_command(self, paths, interpreter_options=None,
                              tool_options=None):
        """
        Build full command line to execute validator tool on given path list.

        Arguments:
            paths (list): List of checkable paths to pass to command line.

        Keyword Arguments:
            interpreter_options (list): List of arguments to pass to interpreter.
            tool_options (list): List of arguments to pass to validator tool.

        Returns:
            list: List of items to build full command line.
        """
        args = self.get_interpreter_part(options=interpreter_options)

        html_checker_application = os.path.abspath(
            os.path.dirname(html_checker.__file__)
        )

        if self.VALIDATOR:
            args.append(
                self.VALIDATOR.format(
                    HTML_CHECKER=html_checker_application
                )
            )

        if tool_options:
            args.extend(self.compile_options(tool_options))

        args.extend(paths)

        return args

    def execute_validator(self, command):
        """
        Execute validator process from given command.

        Arguments:
            command (list): List of command elements.

        Returns:
            subprocess.CompletedProcess: Process output.
        """
        try:
            process = subprocess.check_output(command, stderr=subprocess.STDOUT)
        except FileNotFoundError as e:
            msg = "Unable to reach interpreter to run validator: {}"
            raise ValidatorError(msg.format(e))
        except subprocess.CalledProcessError as e:
            msg = "Validator execution failed: {}"
            raise ValidatorError(msg.format(e.output.decode("utf-8")))

        return process

    def manage_options(self, interpreter_options, tool_options):
        """
        Compile default and additional interpreter and validator options.

        Arguments:
            interpreter_options (dict): Dict of interpreter arguments to
                include in commandline. Default is ``None``.
            tool_options (dict): Dict of validator tool arguments to
                include in commandline. Default is ``None`` but some options
                are defined for internal purposes if not given, such as
                ``--format``, ``--exist-zero-always`` and ``--user-agent``.
                Except the last one, you should not try to change them or you
                will probably break the validator and reporter.

        Returns:
            tuple: Interpreter and validator option lists in a tuple.
        """
        if interpreter_options is None:
            interpreter_options = OrderedDict([])
        if tool_options is None:
            tool_options = OrderedDict([])

        # Enforce JSON format
        if "--format" not in tool_options:
            tool_options["--format"] = "json"

        # Enforce non error exit in order that validator report always goes to
        # the stdout so we can capture it
        if "--exit-zero-always" not in tool_options:
            tool_options["--exit-zero-always"] = None

        # Define default user-agent
        if "--user-agent" not in tool_options:
            tool_options["--user-agent"] = html_checker.USER_AGENT

        return interpreter_options, tool_options

    def validate_item(self, paths, interpreter_options, tool_options):
        """
        Validate a path with validator tool.

        Arguments:
            paths (list): List of page path to validate.
            interpreter_options (dict): Dict of interpreter arguments.
            tool_options (dict): Dict of validator tool arguments.

        Returns:
            subprocess.CompletedProcess: Process output.
        """
        # Build command line from options
        command = self.get_validator_command(
            paths,
            interpreter_options=interpreter_options,
            tool_options=tool_options
        )

        # Execute command process
        return self.execute_validator(command)

    def validate(self, paths, interpreter_options=None,
                 tool_options=None, split=False):
        """
        Perform validation with validator tool for all given paths.

        Arguments:
            paths (list): List of page path to validate.

        Keyword Arguments:
            interpreter_options (dict): Ordered dict of interpreter arguments to
                include in commandline. Default is ``None``.
            tool_options (dict): Ordered dict of validator tool arguments to
                include in commandline. Default is ``None``.
            split (bool): If enabled, each path will be executed in its own
                instance of validator. Else default behavior is to execute
                validator once for all paths.

        Returns:
            html_checker.reporter.ReportStore: Builded report store.
        """
        # Shared options for every validator command execution
        interpreter_options, tool_options = self.manage_options(
            interpreter_options,
            tool_options
        )

        # Ensure uniqueness
        paths = reduce_unique(paths)

        # Init a new ReportStore object
        report = self.REPORT_CLASS(paths)

        # Validate every paths in a single validator execution
        if not split:
            content = self.validate_item(paths, interpreter_options, tool_options)
            report.add(content)
        # Validate each paths on its own validator execution
        else:
            for item in paths:
                content = self.validate_item([item], interpreter_options, tool_options)
                report.add(content)

        return report
