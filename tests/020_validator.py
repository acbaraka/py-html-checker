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


@pytest.mark.parametrize("paths,expected", [
    # Url path
    (
        [
            "http://perdu.com",
        ],
        [
            ("http://perdu.com", None),
        ],
    ),
    # Unexisting file path
    (
        [
            "nope.html",
        ],
        [
            ("nope.html", [{
                "type": "critical",
                "message": "File path does not exists."
            }]),
        ],
    ),
    # Unexisting absolute file path
    (
        [
            "{FIXTURES}/nope.html",
        ],
        [
            ("{FIXTURES}/nope.html", [{
                "type": "critical",
                "message": "File path does not exists."
            }]),
        ],
    ),
    # Relative file path
    (
        [
            "tests/data_fixtures/html/valid.basic.html",
        ],
        [
            ("{FIXTURES}/html/valid.basic.html", None),
        ],
    ),
    # Absolute file path
    (
        [
            "{FIXTURES}/html/valid.basic.html",
        ],
        [
            ("{FIXTURES}/html/valid.basic.html", None),
        ],
    ),
])
def test_build_initial_registry(settings, paths, expected):
    """
    Should build a correct registry of initial values for required path.
    """
    v = ValidatorInterface()

    paths = [settings.format(item) for item in paths]

    expected = [(settings.format(k), v) for k,v in expected]

    assert expected == v.build_initial_registry(paths)


@pytest.mark.parametrize("paths,content,expected", [
    (
        ["foo.html"],
        b"""{"messages":[]}""",
        OrderedDict([
            ("foo.html", [
                {
                    "type": "critical",
                    "message": "File path does not exists."
                },
            ])
        ])
    ),
    (
        ["foo.html"],
        b"""{"messages":[{"url": "http://perdu.com"}]}""",
        OrderedDict([
            ("foo.html", [
                {
                    "type": "critical",
                    "message": "File path does not exists."
                },
            ]),
        ])
    ),
    (
        ["foo.html", "http://perdu.com"],
        b"""{"messages":[]}""",
        OrderedDict([
            ("foo.html", [
                {
                    "type": "critical",
                    "message": "File path does not exists."
                },
            ]),
            ("http://perdu.com", None),
        ])
    ),
    (
        ["foo.html", "http://perdu.com"],
        b"""{"messages":[{"url": "foo.html"}, {"url": "http://perdu.com", "ping": "pong"}, {"url": "http://perdu.com", "pif": "paf"}]}""",
        OrderedDict([
            ("foo.html", [
                {
                    "type": "critical",
                    "message": "File path does not exists."
                },
                {},
            ]),
            ("http://perdu.com", [
                {"ping": "pong"},
                {"pif": "paf"},
            ])
        ])
    ),
])
def test_parse_report(paths, content, expected):
    """
    Path reports should be indexed on their path and contains their full report
    payload.
    """
    v = ValidatorInterface()

    assert expected == v.parse_report(paths, content)


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
    # Multiple sources either unexisting, valid or invalid
    (
        [
            "foo.html",
            "{FIXTURES}/html/valid.basic.html",
            "{FIXTURES}/html/valid.warning.html"
        ],
        [
            ('foo.html', [
                {
                    "type": "critical",
                    "message": "File path does not exists."
                },
            ]),
            (
                "{FIXTURES}/html/valid.basic.html",
                None
            ),
            (
                "{FIXTURES}/html/valid.warning.html",
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
        ]
    ),
    ## Test on an url path, maybe broken some day since it can change
    #(
        #["http://perdu.com"],
        #[
            #[
                #"http://perdu.com",
                #[
                    #{
                        #"type": "error",
                        #"message": "The character encoding was not declared. Proceeding using \u201cwindows-1252\u201d."
                    #},
                    #{
                        #"type": "error",
                        #"message": "Start tag seen without seeing a doctype first. Expected \u201c<!DOCTYPE html>\u201d.",
                        #"extract": "<html><head>",
                        #"firstColumn": 1,
                        #"lastLine": 1,
                        #"hiliteLength": 6,
                        #"lastColumn": 6,
                        #"hiliteStart": 0
                    #},
                    #{
                        #"type": "error",
                        #"message": "Element \u201cpre\u201d not allowed as child of element \u201cstrong\u201d in this context. (Suppressing further errors from this subtree.)",
                        #"extract": "2><strong><pre>    * ",
                        #"firstColumn": 138,
                        #"lastLine": 1,
                        #"hiliteLength": 5,
                        #"lastColumn": 142,
                        #"hiliteStart": 10
                    #},
                    #{
                        #"type": "error",
                        #"message": "Bad character \u201c-\u201d after \u201c<\u201d. Probable cause: Unescaped \u201c<\u201d. Try escaping it as \u201c&lt;\u201d.",
                        #"extract": "pre>    * <----- v",
                        #"firstColumn": 149,
                        #"lastLine": 1,
                        #"hiliteLength": 2,
                        #"lastColumn": 150,
                        #"hiliteStart": 10
                    #},
                    #{
                        #"type": "info",
                        #"message": "Consider adding a \u201clang\u201d attribute to the \u201chtml\u201d start tag to declare the language of this document.",
                        #"extract": "<html><head>",
                        #"firstColumn": 1,
                        #"lastLine": 1,
                        #"subType": "warning",
                        #"hiliteLength": 6,
                        #"lastColumn": 6,
                        #"hiliteStart": 0
                    #}
                #]
            #]
        #]
    #),
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

    assert OrderedDict(final_expection) == report

    #assert 1 == 42


#@pytest.mark.parametrize("paths,splitted,expected", [
    #(
        #["foo.html"],
        #False,
        #OrderedDict([
            #("foo.html", ["foo.html"]),
        #]),
    #),
    #(
        #["foo.html"],
        #True,
        #OrderedDict([
            #("foo.html", ["foo.html"]),
            #("bar.html", ["foo.bar"]),
        #]),
    #),
    #(
        #["foo.html", "bar.html"],
        #False,
        #[],
    #),
    #(
        #["foo.html", "bar.html"],
        #True,
        #[],
    #),
#])
#def test_validate_split(monkeypatch, caplog, settings, paths, splitted, expected):
    #"""
    # DEPRECATED: Useless, was done for 'split' in a wrong way leading to a dead
    # end with reports
    #"""
    #def mock_validator_execute_validator(*args, **kwargs):
        #"""
        #Mock method to just return the passed paths.
        #"""
        #cls = args[0]
        #paths = args[1]
        #print("mock_validator_execute_validator:", paths)
        #return paths

    #def mock_validator_get_validator_command(*args, **kwargs):
        #"""
        #Mock method to just return the passed paths.
        #"""
        #cls = args[0]
        #paths = args[1]
        #print("mock_validator_get_validator_command:", paths)
        #return paths

    #def mock_validator_parse_report(*args, **kwargs):
        #"""
        #Mock method to just return the passed paths.
        #"""
        #cls = args[0]
        #paths = args[1]
        #passed_paths = args[2]
        #print("mock_validator_parse_report:paths:", paths)
        #print("mock_validator_parse_report:passed_paths:", passed_paths)
        #return passed_paths


    #monkeypatch.setattr(ValidatorInterface, "execute_validator",
                        #mock_validator_execute_validator)
    #monkeypatch.setattr(ValidatorInterface, "get_validator_command", mock_validator_get_validator_command)
    #monkeypatch.setattr(ValidatorInterface, "new_parse_report", mock_validator_parse_report)
    #print()
    #v = ValidatorInterface()

    #paths = [settings.format(item) for item in paths]

    ## Rebuild expected data to include fixtures path
    #final_expection = []
    #for item_path, data in expected:
        #final_expection.append(
            #(settings.format(item_path), data)
        #)

    ##report = v.validate(paths)
    #report = v.new_validate(paths, split=splitted)

    #assert OrderedDict(final_expection) == report

    #assert 1 == 42
