def validate(value):
    if value <= 0:
        raise ValueError("negative")
    return value
