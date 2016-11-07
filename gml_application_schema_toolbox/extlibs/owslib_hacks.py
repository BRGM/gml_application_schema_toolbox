try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

#from owslib.feature import WebFeatureService_
from owslib.feature.wfs200 import WebFeatureService_2_0_0


def getGETGetFeatureRequest_2_0_0(self, typename=None, filter=None, bbox=None, featureid=None,
                   featureversion=None, propertyname=None, maxfeatures=None,storedQueryID=None, storedQueryParams=None,
                   outputFormat=None, method='Get', startindex=None):
    storedQueryParams = storedQueryParams or {}

    base_url = next((m.get('url') for m in self.getOperationByName('GetFeature').methods if m.get('type').lower() == method.lower()))
    base_url = base_url if base_url.endswith("?") else base_url+"?"

    request = {'service': 'WFS', 'version': self.version, 'request': 'GetFeature'}

    # check featureid
    if featureid:
        request['featureid'] = ','.join(featureid)
    elif bbox:
        request['bbox'] = self.getBBOXKVP(bbox,typename)
    elif filter:
        request['query'] = str(filter)
    if typename:
        typename = [typename] if type(typename) == type("") else typename
        if int(self.version.split('.')[0]) >= 2:
            request['typenames'] = ','.join(typename)
        else:
            request['typename'] = ','.join(typename)
    if propertyname: 
        request['propertyname'] = ','.join(propertyname)
    if featureversion: 
        request['featureversion'] = str(featureversion)
    if maxfeatures:
        if int(self.version.split('.')[0]) >= 2:
            request['count'] = str(maxfeatures)
        else:
            request['maxfeatures'] = str(maxfeatures)
    if startindex:
        request['startindex'] = str(startindex)
    if storedQueryID: 
        request['storedQuery_id']=str(storedQueryID)
        for param in storedQueryParams:
            request[param]=storedQueryParams[param]
    if outputFormat is not None:
        request["outputFormat"] = outputFormat

    data = urlencode(request)

    return base_url+data


WebFeatureService_2_0_0.getGETGetFeatureRequest = getGETGetFeatureRequest_2_0_0
