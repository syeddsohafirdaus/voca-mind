"""Regional crisis support information."""

INDIA_CRISIS_RESOURCES = (
    "If you are in India:\n"
    "- Immediate danger: Call 112 or visit the nearest "
    "emergency department.\n"
    "- Mental health support: Tele-MANAS offers "
    "24-hour support at 14416 or 1800-891-4416.\n"
    "- Official website: https://telemanas.mohfw.gov.in/\n"
)

INTERNATIONAL_CRISIS_RESOURCES = (
    "If you are outside India, contact your local emergency "
    "services if you are in immediate danger. "
    "For local crisis helplines, visit "
    "https://findahelpline.com or https://befrienders.org."
)


def get_crisis_resources() -> str:
    return (
        INDIA_CRISIS_RESOURCES
        + "\n"
        + INTERNATIONAL_CRISIS_RESOURCES
    )
