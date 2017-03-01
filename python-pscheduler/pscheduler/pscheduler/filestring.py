"""
Functions for retrieving strings from files
"""


def string_from_file(string, strip=True):
    """
    Return an unaltered string or the contents of a file if the string
    begins with @ and the rest of it points at a path.

    If 'strip' is True, remove leading and trailing whitespace
    (default behavior).
    """

    if string[0] != "@":

        value = string

    else:

        with open(string[1:], 'r') as content:
            value = content.read()

    return value.strip() if strip else value


if __name__ == "__main__":
    print string_from_file("Plain string")
    print string_from_file("@/etc/fstab")
    try:
        print string_from_file("@/invalid/path")
    except Exception as ex:
        print "FAILED: " + str(ex)
