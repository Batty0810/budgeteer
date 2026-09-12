from app.models.category import DEFAULT_CATEGORY_COLORS


def next_category_color(existing_count):
    """Pick the next colour in the validated categorical sequence.

    Cycling by count (rather than letting the caller choose freely) keeps
    each category's colour stable over time - charts never repaint an
    existing category when a new one is added or the list is filtered.
    """
    return DEFAULT_CATEGORY_COLORS[existing_count % len(DEFAULT_CATEGORY_COLORS)]
