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
import xml.etree.ElementTree as ET

def extract_features(doc):
    """Extract (Complex) features from a XML doc
    :param doc: a DOM document
    :returns: (bbox, bbox_srs, nodes)
              where bbox is a rectangle (xmin, ymin, xmax, ymax) representing a bounding box
                    bbox_srs is the srsName of the bbox
                    nodes is a list of nodes for each feature
    """
    def _extract(node):
        features = []
        bbox = None
        bbox_srs = None
        if node.tag.startswith(u'{http://www.opengis.net/wfs') and node.tag.endswith('FeatureCollection'):
            # WFS features
            for child in node:
                if no_prefix(child.tag) == 'member':
                    # a member may contain another featurecollection => recursive call
                    for cchild in child:
                        nbbox, nbbox_srs, nfeatures = _extract(cchild)
                        if bbox is None:
                            bbox = nbbox
                            bbox_srs = nbbox_srs
                        features += nfeatures
                elif no_prefix(child.tag) == 'featureMembers':
                    for cchild in child:
                        features.append(cchild)
                elif no_prefix(child.tag) == 'featureMember':
                    for cchild in child:
                        features.append(cchild)
                elif no_prefix(child.tag) == 'boundedBy':
                    lc = None
                    uc = None
                    for cchild in child:
                        if no_prefix(cchild.tag) == 'Envelope':
                            for k, v in cchild.attrib.items():
                                if no_prefix(k) == 'srsName':
                                    bbox_srs = v
                            for ccchild in cchild:
                                if no_prefix(ccchild.tag) == 'lowerCorner':
                                    lc = ccchild.text
                                elif no_prefix(ccchild.tag) == 'upperCorner':
                                    uc = ccchild.text
                    if lc is not None and uc is not None:
                        lcp = [float(x) for x in lc.split(' ')]
                        ucp = [float(x) for x in uc.split(' ')]
                        bbox = (lcp[0], lcp[1], ucp[0], ucp[1])
                        
        elif node.tag.startswith(u'{http://www.opengis.net/sos/2') and node.tag.endswith('GetObservationResponse'):
            # SOS features
            for child in node:
                if no_prefix(child.tag) == "observationData":
                    features.append(child[0])
        else:
            # it seems to be an isolated feature
            features.append(node)
        return (bbox, bbox_srs, features)
    return _extract(doc.getroot())

def extract_features_from_file(file_path):
    return extract_features(ET.parse(file_path))
