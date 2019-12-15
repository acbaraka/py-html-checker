import os
from collections import OrderedDict

import pytest

from html_checker.validator import ValidatorInterface

from html_checker.exceptions import (PathInvalidError, SitemapInvalidError,
                              ValidatorError)


@pytest.mark.parametrize("options,expected", [
    (
        {
            "--foo": "bar",
        },
        ["--foo", "bar"],
    ),
    (
        {
            "-f": None
        },
        ["-f"],
    ),
    (
        OrderedDict([
            ("--foo", "bar"),
            ("-a", None),
            ("--plip", "plop"),
            ("-b", "c"),
        ]),
        [
            "--foo", "bar",
            "-a",
            "--plip", "plop",
            "-b", "c",
        ],
    ),
])
def test_compile_options(options, expected):
    """
    Should flatten to a list any kind of options
    """
    v = ValidatorInterface()

    assert expected == v.compile_options(options)


@pytest.mark.parametrize("interpreter,options,expected", [
    (
        "",
        {},
        [],
    ),
    (
        None,
        {},
        ["java", "-jar"],
    ),
    (
        None,
        {"-Xss512k": None},
        ["java", "-Xss512k", "-jar"],
    ),
    (
        "machin",
        {},
        ["machin"],
    ),
])
def test_get_interpreter_part(interpreter, options, expected):
    """
    Should return command for interpreter part
    """
    v = ValidatorInterface()

    if interpreter is not None:
        v.INTERPRETER = interpreter

    assert expected == v.get_interpreter_part(options=options)


@pytest.mark.parametrize("interpreter,validator,interpreter_options,tool_options,paths,expected", [
    (
        None,
        None,
        [],
        [],
        ["foo.html"],
        ["java", "-jar", "{APPLICATION}/vnujar/vnu.jar", "foo.html"],
    ),
    (
        None,
        "",
        [],
        [],
        ["foo.html"],
        ["java", "-jar", "foo.html"],
    ),
    (
        None,
        "dummytool",
        [],
        [],
        ["foo.html"],
        ["java", "-jar", "dummytool", "foo.html"],
    ),
    (
        "dummycli",
        "validate",
        {"-v": "3"},
        {"--foo": "bar"},
        ["foo.html", "bar.html"],
        ["dummycli", "-v", "3", "validate", "--foo", "bar", "foo.html",
         "bar.html"],
    ),
])
def test_get_validator_command(settings, interpreter, validator,
                               interpreter_options, tool_options, paths,
                               expected):
    """
    Should return full command line to execute validator tool for given path
    list.

    To avoid hardcoding absolute path in test parameters, expected paths is
    formatted to be prepend with application path if starting with
    ``{APPLICATION}``.
    """
    v = ValidatorInterface()

    if interpreter is not None:
        v.INTERPRETER = interpreter

    if validator is not None:
        v.VALIDATOR = validator

    expected = [settings.format(item) for item in expected]

    cmd = v.get_validator_command(
        paths,
        interpreter_options=interpreter_options,
        tool_options=tool_options
    )

    assert expected == cmd


@pytest.mark.parametrize("interpreter,validator,interpreter_options,tool_options,paths,expected", [
    # Unreachable interpreter
    (
        "nietniet",
        None,
        {},
        {},
        ["http://perdu.com"],
        "Unable to reach interpreter to run validator: [Errno 2] No such file or directory: 'nietniet'",
    ),
    # Unreachable validator
    (
        None,
        "nietniet",
        {},
        {},
        ["http://perdu.com"],
        "Validator execution failed: Error: Unable to access jarfile nietniet\n",
    ),
    # Wrong option on validator (wrong option on interpreter are ignored)
    (
        None,
        None,
        {"--bizarro": None},
        {},
        ["http://perdu.com"],
        ("Validator execution failed: Unrecognized option: --bizarro\n"
         "Error: Could not create the Java Virtual Machine.\n"
         "Error: A fatal exception has occurred. Program will exit.\n"),
    ),
])
def test_validate_fail(settings, interpreter, validator,
                       interpreter_options, tool_options, paths, expected):
    """
    Exception should be raised when there is an error while executing
    interpreter or validator. Note than validator won't throw any error when
    pages to check is missing, invalid, etc..
    """
    v = ValidatorInterface()

    paths = [settings.format(item) for item in paths]

    if interpreter is not None:
        v.INTERPRETER = interpreter

    if validator is not None:
        v.VALIDATOR = validator

    with pytest.raises(ValidatorError) as excinfo:
        v.validate(
            paths,
            interpreter_options=interpreter_options,
            tool_options=tool_options
        )

    assert expected == str(excinfo.value)


@pytest.mark.parametrize("paths,expected", [
    # Unexisting file dont fail, just return an empty item
    (
        ["foo.html"],
        [
            ('foo.html', [
                {
                    "type": "critical",
                    "message": "File path does not exists."
                },
            ]),
        ],
    ),
    # Simple valid source just return an empty item
    (
        ["{FIXTURES}/html/valid.basic.html"],
        [('{FIXTURES}/html/valid.basic.html', None)],
    ),
    #
    (
        ["tests/data_fixtures/html/valid.basic.html"],
        [('{PACKAGE}/tests/data_fixtures/html/valid.basic.html', None)],
    ),
])
def test_validate_success(caplog, settings, paths, expected):
    """
    Should get a correct report from validator tool process for given path list.
    """
    v = ValidatorInterface()

    paths = [settings.format(item) for item in paths]

    # Rebuild expected data to include fixtures path
    final_expection = []
    for item_path, data in expected:
        final_expection.append(
            (settings.format(item_path), data)
        )

    report = v.validate(paths)

    assert OrderedDict(final_expection) == report.registry


def test_validate_split_one_path(caplog, settings):
    """
    "validate" method return should return the same report for a single path
    when split is enabled or disabled.
    """
    v = ValidatorInterface()

    splitted = v.validate(
        [settings.format("{FIXTURES}/html/valid.warning.html")],
        split=True
    )

    single = v.validate(
        [settings.format("{FIXTURES}/html/valid.warning.html")],
        split=True
    )

    assert single.registry == OrderedDict([
        (
            settings.format("{FIXTURES}/html/valid.warning.html"),
            [
                {
                    "lastColumn": 6,
                    "subType": "warning",
                    "firstLine": 1,
                    "extract": "type html>\n<html>\n<head",
                    "hiliteStart": 10,
                    "hiliteLength": 7,
                    "message": "Consider adding a \u201clang\u201d attribute to the \u201chtml\u201d start tag to declare the language of this document.",
                    "lastLine": 2,
                    "type": "info",
                    "firstColumn": 16
                }
            ]
        )
    ])

    assert splitted.registry == single.registry


def test_validate_split_many_paths(caplog, settings):
    """
    "validate" method return should return the same report for multiple paths
    when split is enabled or disabled.
    """
    v = ValidatorInterface()

    paths = [
        "foo.html",
        settings.format("{FIXTURES}/html/valid.basic.html"),
        settings.format("{FIXTURES}/html/valid.warning.html")
    ]

    splitted = v.validate(
        paths,
        split=True
    )

    single = v.validate(
        paths,
        split=True
    )

    assert single.registry == OrderedDict([
        ('foo.html', [
            {
                "type": "critical",
                "message": "File path does not exists."
            },
        ]),
        (
            settings.format("{FIXTURES}/html/valid.basic.html"),
            None
        ),
        (
            settings.format("{FIXTURES}/html/valid.warning.html"),
            [
                {
                    "lastColumn": 6,
                    "subType": "warning",
                    "firstLine": 1,
                    "extract": "type html>\n<html>\n<head",
                    "hiliteStart": 10,
                    "hiliteLength": 7,
                    "message": "Consider adding a \u201clang\u201d attribute to the \u201chtml\u201d start tag to declare the language of this document.",
                    "lastLine": 2,
                    "type": "info",
                    "firstColumn": 16
                }
            ]
        )
    ])

    assert splitted.registry == single.registry
