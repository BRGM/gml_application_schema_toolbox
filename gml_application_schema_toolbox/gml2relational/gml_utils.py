from xml_utils import no_prefix

def extract_features(doc):
    """Extract (Complex) features from a XML doc
    :param doc: a DOM document
    :returns: a list of nodes for each feature
    """
    nodes = []
    root = doc.getroot()
    if root.tag.startswith(u'{http://www.opengis.net/wfs') and root.tag.endswith('FeatureCollection'):
        # WFS features
        for child in root:
            if no_prefix(child.tag) == 'member':
                nodes.append(child[0])
            elif no_prefix(child.tag) == 'featureMembers':
                for cchild in child:
                    nodes.append(cchild)
    elif root.tag.startswith(u'{http://www.opengis.net/sos/2') and root.tag.endswith('GetObservationResponse'):
        # SOS features
        for child in root:
            if no_prefix(child.tag) == "observationData":
                nodes.append(child[0])
    else:
        # it seems to be an isolated feature
        nodes.append(root)
    return nodes
