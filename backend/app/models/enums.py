from enum import StrEnum


class UserRole(StrEnum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class Representation(StrEnum):
    """How a question is presented to the student (the 'surface form')."""

    NUMERIC = "numeric"  # bare values, e.g. "u = 3, a = 2, t = 5. Find v."
    WORD = "word"  # prose description of a situation
    GRAPH = "graph"  # read from / reason about a motion graph
    TABLE = "table"  # data given in a table
    DIAGRAM = "diagram"  # labelled sketch or set-up description


class Correctness(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    INVALID = "invalid"  # answer could not be parsed as a number


class ErrorType(StrEnum):
    CORRECT = "CORRECT"
    ARITHMETIC_ERROR = "ARITHMETIC_ERROR"
    VARIABLE_IDENTIFICATION_ERROR = "VARIABLE_IDENTIFICATION_ERROR"
    FORMULA_SELECTION_ERROR = "FORMULA_SELECTION_ERROR"
    SIGN_ERROR = "SIGN_ERROR"
    UNIT_ERROR = "UNIT_ERROR"
    MULTI_STEP_ERROR = "MULTI_STEP_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
