def no_prefix(tag):
    """Remove the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[tag.rfind('}')+1:]
    return tag

def prefix(tag):
    """Return the namespace prefix from the given name"""
    if tag.startswith('{'):
        return tag[1:tag.rfind('}')]
    return ""

def split_tag(tag):
    """Return a pair (ns prefix, tag) from a tag name"""
    if tag.startswith('{'):
        i = tag.rfind('}')
        return (tag[1:i], tag[i+1:])
    return ("", tag)

