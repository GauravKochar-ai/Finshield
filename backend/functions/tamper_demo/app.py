"""tamper_demo: STUB. Logs the event and returns OK. Owner replaces handle() with real code (see .kiro/specs)."""
from finshield import stub


def handler(event, context):
    return stub.handle("tamper_demo", event, context)
