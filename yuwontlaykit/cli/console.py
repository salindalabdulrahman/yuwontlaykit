"""Colored console I/O for the Yuwontlaykit CLI."""

from __future__ import annotations

from colorama import Fore, Style

_prompt_label = "Boss"


def set_prompt_label(label: str) -> None:
    global _prompt_label
    _prompt_label = label


def print_assistant(message: str) -> None:
    print(f"\n{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} {message}\n")


def print_banner(message: str) -> None:
    print(f"{Fore.GREEN}{message}{Style.RESET_ALL}\n")


def print_status(message: str) -> None:
    """Quiet progress line during diagnostics — not a full assistant turn."""
    print(f"{Fore.MAGENTA}  …{Style.RESET_ALL} {message}")


def prompt_user() -> str:
    return input(f"{Fore.YELLOW}{_prompt_label} > {Style.RESET_ALL}")


def print_goodbye(name: str | None = None) -> None:
    who = name or _prompt_label
    print(f"{Fore.CYAN}Yuwontlaykit >{Style.RESET_ALL} Goodbye, {who}!")
