def r_replace(string: str, _old: str, _new: str, count: int = 1) -> str:
    """Replaces occurances of _old with _new but starting from the end of the string working to the start.

    Args:
        string (str): The string to replace the characters in.
        _old (str): The old string to replace.
        _new (str): The new string to replace with.
        count (int, optional): Limit how many occurances of _old to replace. Defaults to 1.

    Returns:
        str: _description_
    """
    return _new.join(string.rsplit(_old, count))
