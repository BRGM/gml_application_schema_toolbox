#   Copyright (C) 2016 BRGM (http:///brgm.fr)
#   Copyright (C) 2016 Oslandia <infos@oslandia.com>
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Library General Public
#   License as published by the Free Software Foundation; either
#   version 2 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Library General Public License for more details.
#   You should have received a copy of the GNU Library General Public
#   License along with this library; if not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import
# -*- coding: utf-8 -*-
from .xml_utils import no_prefix

def extract_features(doc):
    """Extract (Complex) features from a XML doc
    :param doc: a DOM document
    :returns: a list of nodes for each feature
    """
    def _extract(node):
        features = []
        if node.tag.startswith(u'{http://www.opengis.net/wfs') and node.tag.endswith('FeatureCollection'):
            # WFS features
            for child in node:
                if no_prefix(child.tag) == 'member':
                    # a member may contain another featurecollection => recursive call
                    for cchild in child:
                        features += _extract(cchild)
                elif no_prefix(child.tag) == 'featureMembers':
                    for cchild in child:
                        features.append(cchild)
        elif node.tag.startswith(u'{http://www.opengis.net/sos/2') and node.tag.endswith('GetObservationResponse'):
            # SOS features
            for child in node:
                if no_prefix(child.tag) == "observationData":
                    features.append(child[0])
        else:
            # it seems to be an isolated feature
            features.append(node)
        return features
    return _extract(doc.getroot())
