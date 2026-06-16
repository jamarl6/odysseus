"""Lightweight routing hints for chat requests that need tools.

These patterns are intentionally conservative. They only promote plain chat
to agent mode when the user asks the assistant to take an action, not when the
user asks how a feature works.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Pattern


@dataclass(frozen=True)
class ToolIntent:
    """A cheap, deterministic chat-to-agent routing decision."""

    needs_tools: bool
    category: str = ""
    reason: str = ""


_ACTION_QUESTION = r"\b(?:can|could|would|will|kannst|könntest|würdest|wirst)\s+(?:you|du)\s+"
_ACTION_FOLLOWUP = (
    r"\b(?:you\s+should\s+be\s+able\s+to|"
    r"(?:can|could|would|will|should)\s+you|"
    r"you\s+(?:can|could|would|will|should|need\s+to|have\s+to)|"
    r"du\s+solltest|"
    r"(?:kannst|könntest|würdest|wirst|solltest)\s+du|"
    r"du\s+(?:kannst|könntest|würdest|wirst|solltest|musst|brauchst))\s+"
)
_PLEASE = r"^\s*(?:(?:please|ok(?:ay)?|alright|right|sure|cool|great|thanks|bitte|alles\s+klar|klar|sicher|super|danke)[\s,.!-]+)*"

_CALENDAR_ACTION = (
    r"(?:add|adding|create|creating|recreate|recreating|schedule|scheduling|"
    r"reschedule|rescheduling|book|booking|put|set\s+up|make|making|"
    r"delete|deleting|remove|removing|cancel|cancelling|canceling|"
    r"füge|trage|erstell|mach|plan|buch|setz|lösch|entfern|sag\s+ab)"
)
_CALENDAR_THING = r"(?:calendar|calendar\s+(?:entry|item)|event|meeting|appointment|entry|call|kalender|termin|besprechung|meeting|eintrag|kalendereintrag|ereignis)"
_CALENDAR_READ_THING = r"(?:calendar|schedule|events?|meetings?|appointments?|classes?|kalender|termine?|besprechungen?|einträge|ereignisse)"
_EXPLANATORY_PREFIX = re.compile(
    r"^\s*(?:how\s+(?:do|can)\s+i|can\s+you\s+explain|what\s+about|tell\s+me\s+how|show\s+me\s+how|"
    r"wie\s+(?:mache|kann)\s+ich|kannst\s+du\s+erklären|erkläre\s+mir|zeig\s+mir\s+wie)\b",
    re.I,
)

_PANEL = (
    r"(?:calendar|notes?|inbox|email|mail|documents?|docs|library|gallery|"
    r"settings|cookbook|sessions?|chats?|skills|memories|memory|brain|"
    r"kalender|notizen?|posteingang|dokumente?|bibliothek|galerie|"
    r"einstellungen|sitzungen?|gedächtnis|gehirn|erinnerungen?)"
)

_ROUTING_PATTERNS: tuple[tuple[str, str, Pattern[str]], ...] = tuple(
    (category, reason, re.compile(pattern, re.I))
    for category, reason, pattern in (
        # Calendar/event creation. Covers "Can you add an entry to my
        # calendar?", imperatives like "add lunch to my calendar", and
        # follow-ups such as "you should be able to create that event now".
        ("calendar", "assistant calendar action request", rf"{_ACTION_QUESTION}{_CALENDAR_ACTION}\b.{{0,120}}\b{_CALENDAR_THING}\b"),
        ("calendar", "calendar follow-up action request", rf"{_ACTION_FOLLOWUP}{_CALENDAR_ACTION}\b.{{0,120}}\b{_CALENDAR_THING}\b"),
        ("calendar", "calendar imperative action request", rf"{_PLEASE}{_CALENDAR_ACTION}\b.{{0,120}}\b{_CALENDAR_THING}\b"),
        ("calendar", "calendar target action request", rf"{_PLEASE}{_CALENDAR_ACTION}\b.{{0,120}}\b(?:to|on|in|into|for)\s+(?:my\s+|the\s+|this\s+)?calendar\b"),
        ("calendar", "calendar item action request", rf"{_PLEASE}{_CALENDAR_ACTION}\s+(?:it\s+)?(?:a\s+|an\s+)?(?:calendar\s+)?(?:event|meeting|appointment|entry|item|call)\b"),
        ("calendar", "calendar target action request", rf"\b{_CALENDAR_ACTION}\b.{{0,120}}\b(?:to|on|in|into|for)\s+(?:my\s+|the\s+|this\s+)?calendar\b"),
        ("calendar", "put item on calendar request", r"\bput\s+.+\bon\s+(?:my\s+)?calendar\b"),

        # Calendar/event lookup. A question such as "Do I have Taekwondo
        # classes this week?" needs the calendar tool; plain chat cannot know.
        ("calendar", "calendar lookup request", rf"\b(?:list|show|check|find)\b.{{0,120}}\b(?:my\s+|the\s+)?(?:upcoming|next|today'?s?|tomorrow'?s?|this\s+week'?s?)\b.{{0,120}}\b{_CALENDAR_READ_THING}\b"),
        ("calendar", "calendar lookup question", rf"\b(?:what|which)\b.{{0,120}}\b(?:upcoming|next|today'?s?|tomorrow'?s?|this\s+week'?s?)\b.{{0,120}}\b{_CALENDAR_READ_THING}\b"),
        ("calendar", "calendar availability question", rf"\bdo\s+i\s+have\b.{{0,120}}\b(?:upcoming|next|today|tomorrow|this\s+week)\b.{{0,120}}\b{_CALENDAR_READ_THING}\b"),
        ("calendar", "calendar agenda question", r"\bwhat(?:'s| is)\s+on\s+(?:my\s+)?calendar\b"),
        ("calendar", "next calendar item question", r"\bwhen\s+(?:is|are)\s+(?:my\s+)?next\s+(?:event|meeting|appointment|class)\b"),

        # Notes, todos, checklists, and reminders.
        ("notes", "reminder request", r"\b(?:remind|erinnere)\s+m(?:e|ich)\b"),
        ("notes", "assistant note/todo action request", rf"{_ACTION_QUESTION}(?:add|create|make|take|jot|write\s+down|set|erstell|mach|schreib|notier|setz|füge)\b.{{0,120}}\b(?:note|todo|task|checklist|reminder|notiz|aufgabe|erinnerung)\b"),
        ("notes", "note/todo imperative request", rf"{_PLEASE}(?:add|create|make|erstell|mach|schreib|notier|setz|füge)\s+(?:a\s+|an\s+|eine\s+|ein\s+)?(?:todo|task|reminder|note|checklist|notiz|aufgabe|erinnerung)\b"),
        ("notes", "take note request", rf"{_PLEASE}(?:take|jot|write\s+down|schreib|notier)\s+(?:a\s+|an\s+|eine\s+)?(?:note|notiz)\b"),
        ("notes", "add item to notes/todo request", rf"{_PLEASE}(?:add|jot|write\s+down|füge|schreib|notier)\b.{{0,120}}\b(?:to|in|into|zu|auf)\s+(?:my\s+|the\s+|meine\s+|die\s+)?(?:todo(?:\s+list)?|task\s+list|notes?|checklist|notiz|aufgabe)\b"),
        ("notes", "set reminder request", rf"{_PLEASE}(?:set|setz)\s+(?:a\s+|eine\s+)?(?:reminder|erinnerung)\b"),
        ("notes", "assistant reminder request", rf"{_ACTION_QUESTION}(?:set|setz)\s+(?:a\s+|eine\s+)?(?:reminder|erinnerung)\b"),

        # Email actions.
        ("email", "assistant email action request", rf"{_ACTION_QUESTION}(?:send|write|reply|email|message|archive|delete|mark|schreib|antwort|lösch|archivier|markier|sende)\b.{{0,120}}\b(?:emails?|mail|messages?|inbox|unread|read|nachrichten?|posteingang)\b"),
        ("email", "send/write/reply email request", rf"{_PLEASE}(?:send|write|reply|schreib|antwort|sende)\b.{{0,120}}\b(?:emails?|mail|messages?|nachrichten?)\b"),
        ("email", "archive/delete/mark email request", rf"{_PLEASE}(?:archive|delete|mark|archivier|lösch|markier)\b.{{0,120}}\b(?:emails?|mail|messages?|inbox|nachrichten?|posteingang)\b"),
        ("email", "email composition request", r"\b(?:send|write|reply|schreib|antwort|sende)\s+(?:an?\s+|eine\s+)?(?:email|message|mail|nachricht)\b"),
        ("email", "email contact request", r"\bemail\s+\w+\b"),
        ("email", "check inbox request", r"\b(?:check|prüfe|zeige)\s+(?:my\s+|meinen\s+)?(?:email|inbox|mail|posteingang)\b"),
        ("email", "unread email request", r"\b(?:unread|ungelesene)\s+(?:email|mail|nachrichten?)s?\b"),

        # UI/control-plane actions that should open panels or flip toggles.
        ("ui", "open/show panel request", rf"{_PLEASE}(?:open|show|bring\s+up)\s+(?:me\s+)?(?:my\s+|the\s+)?{_PANEL}\b"),
        ("ui", "tool or feature toggle request", r"\b(?:disable|enable|turn\s+(?:on|off))\s+(?:the\s+)?(?:shell|search|web|browser|documents?|memory|skills|images?|calendar|email|mail|research|incognito)\b"),

        # Deep research jobs, not quick conceptual mentions of research.
        ("web", "explicit web search request", rf"{_PLEASE}(?:do|run|use|perform|make)\s+(?:a\s+)?(?:web\s+search|search\s+the\s+web)\b.+"),
        ("web", "explicit web search request german", rf"{_PLEASE}(?:mache|führe|starte)\s+(?:eine\s+)?(?:websuche|suche\s+im\s+internet)\b.+"),
        ("web", "web lookup imperative request", rf"{_PLEASE}(?:web\s+search|search\s+the\s+web|search\s+online|look\s+up|google|suche\s+im\s+internet|suche\s+im\s+web|google\s+nach)\b.+"),
        ("web", "assistant web lookup request", rf"{_ACTION_QUESTION}(?:web\s+search|search\s+the\s+web|search\s+online|look\s+up|google|im\s+internet\s+suchen?|im\s+web\s+suchen?|nachschauen)\b.+"),
        ("research", "deep research imperative request", rf"{_PLEASE}(?:research|deep\s+dive|look\s+into|investigate)\s+.+"),
        ("research", "assistant deep research request", rf"{_ACTION_QUESTION}(?:research|do\s+research|deep\s+dive|look\s+into|investigate)\s+.+"),

        # Shell / remote-host intent.
        ("shell", "ssh request", r"\bssh\s+(?:in)?to\b"),
        ("shell", "ssh target request", r"\bssh\s+\w+"),
        ("shell", "remote command request", r"\b(run|execute)\s+.{1,40}\bon\s+\w+"),
        ("shell", "assistant command execution request", r"\b(can|could|please|would)\s+you\s+(run|execute|exec)\b"),
        # Shell verbs only count in imperative position (start of message,
        # optionally after "please") or as a "can you ..." request. A bare
        # word match promoted informational questions ("What does the grep
        # command do?") and incidental uses ("My cat ate my homework").
        ("shell", "imperative shell command request", rf"{_PLEASE}(deploy|build|install|restart|reboot|kill|tail|grep|cat|ls|cd|cp|mv|rm)\b\s+\S+"),
        ("shell", "assistant shell command request", rf"{_ACTION_QUESTION}(deploy|build|install|restart|reboot|kill|tail|grep|cat|ls|cd|cp|mv|rm)\b\s+\S+"),
        ("shell", "system/file check request", r"\b(check|see)\s+(if|whether|what)\s+.{1,40}\b(running|process|service|port|file|exists?)\b"),
    )
)

_TOOL_INTENT_PATTERNS: tuple[Pattern[str], ...] = tuple(
    pattern for _, _, pattern in _ROUTING_PATTERNS
)


def classify_tool_intent(text: str) -> ToolIntent:
    """Classify whether a chat message should be promoted to agent mode."""
    if not text:
        return ToolIntent(False, reason="empty message")
    if _EXPLANATORY_PREFIX.search(text):
        return ToolIntent(False, reason="explanatory feature question")
    for category, reason, pattern in _ROUTING_PATTERNS:
        if pattern.search(text):
            return ToolIntent(True, category=category, reason=reason)
    return ToolIntent(False, reason="no tool-action pattern matched")


def message_needs_tools(text: str, patterns: Iterable[Pattern[str]] = _TOOL_INTENT_PATTERNS) -> bool:
    """Return True when a plain chat message should be promoted to agent mode."""
    if not text:
        return False
    if _EXPLANATORY_PREFIX.search(text):
        return False
    if patterns is _TOOL_INTENT_PATTERNS:
        return classify_tool_intent(text).needs_tools
    return any(pattern.search(text) for pattern in patterns)
