"""Argument-parser rendering with the shared diagnostic redaction policy."""

from argparse import ArgumentParser

from aris.core.redaction import redact_text


class DiagnosticArgumentParser(ArgumentParser):
    def _print_message(self, message, file=None):
        # Covers usage, error text, and exit messages, including subparsers.
        # Parsing, exit codes, and parsed argument values remain unchanged.
        super()._print_message(redact_text(message) if message else message, file)
