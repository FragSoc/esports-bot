"""
The lib package was partially copied over from the BASED template project: https://github.com/Trimatix/BASED
It is modified and not actively synced with BASED, so will very likely be out of date.

.. codeauthor:: Trimatix
"""

import traceback


def print_exception_trace(e: Exception):
    """Prints the trace for an exception into stdout.
    Great for debugging errors that are swallowed by the event loop.

    :param Exception e: The exception whose stack trace to print
    """
    traceback.print_exception(type(e), e, e.__traceback__)
