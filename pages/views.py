
from django.views import View
from django.views.generic import FormView
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

import requests
import xmltodict
from elasticsearch import Elasticsearch
from requests.adapters import HTTPAdapter
from requests.exceptions import RetryError
from urllib3.util import Retry
from xml.dom import minidom
import xml.etree.ElementTree as ET
import os

class FrontPage(View):
    template_name = 'base.html'

    def get(self, request):
        return render(request, '404.html',{})

# Create your views here.
def format_mem(m: int):
    suffix = ['B','KB','MB','GB','TB','PB']
    index = 0

    while m > 1:
        m = m/1000
        index += 1
    m = f'{m*1000:.2f}'
    return f'{m} {suffix[index-1]}'

ns = {'cci': 'http://a9.com/-/spec/opensearch/1.1/',
      'ceda': 'http://localhost/ceda/opensearch',
      'eo': 'http://a9.com/-/opensearch/extensions/eo/1.0/',
      'geo': 'http://a9.com/-/opensearch/extensions/geo/1.0/',
      'safe': 'http://www.esa.int/safe/sentinel/1.1',
      'time': 'http://a9.com/-/opensearch/extensions/time/1.0/',
      'param': 'http://a9.com/-/spec/opensearch/extensions/parameters/1.0/',
      'sru': 'http://a9.com/-/opensearch/extensions/sru/2.0/'
     }

class FrontPage(View):
    template_name = 'base.html'

    def get(self, request):
        return render(request, '404.html',{})


class BasicJSONView(View):
    
    def get(self, request, uuid):
        print(uuid)
        return JsonResponse(
            requests.get(f'https://catalogue.ceda.ac.uk/api/v2/observations.json?uuid={uuid}').json()
        )
    
def _fetch_url(_url):
    """
    Method for fetching the xml description for a dataset from Moles Gemini.
    
    Session mounting opensearch 'mounts a custom adapter to a given schema'
    """

    retries = Retry(
        total=3,
        backoff_factor=4,
        status_forcelist=[500],
        allowed_methods=["GET"]
    )

    opensearch_url = 'https://opensearch-test.ceda.ac.uk/opensearch/description.xml'

    result, response, error = None, None, False
    opensearch_adapter = HTTPAdapter(max_retries=retries)
    with requests.Session() as session:
        session.mount(opensearch_url, opensearch_adapter)
        session.mount(opensearch_url, opensearch_adapter)
        try:
            response = session.get(_url )
        except ConnectionError as ce:
            print(ce)
            error = True
            pass
        except RetryError as re:
            print(re)
            error = True
            pass

    if response is not None:
        if response.status_code == 200:
            result = response.content
        else:
            print("Response status: " + str(response.status_code))
            result = None
            error = True
    else:
        print("Response to '" + str(_url)  + "' undefined")
        result = None
        error = True

    return (result, error)
    
def get_user_guide(uuid) -> str:
    """
    Obtain the link to the product user guide.
    
    This is scraped from the Moles gemini link below, which contains an xml document
    with this element. The code for selecting the user guide was taken from the 
    `cci-opensearch-ecv-parser-1.py` script provided by Ambient.
    """

    describedby_url = f'https://catalogue.ceda.ac.uk/export/xml/gemini2.3/{uuid}.xml'

    (describedbyXML, status_code) = _fetch_url(describedby_url)
    mydoc  = minidom.parseString(describedbyXML)

    guide, doi = None, ''
    
    onlineResources = mydoc.getElementsByTagName('gmd:CI_OnlineResource')
    for onlineResource in onlineResources:
        name = onlineResource.getElementsByTagName('gmd:name')
        name_elem = name[0].getElementsByTagName('gco:CharacterString')
        name_str = (name_elem[0].firstChild.nodeValue).lower()
        url_elem = onlineResource.getElementsByTagName('gmd:URL')
        url = url_elem[0].firstChild.nodeValue
        if 'product user guide' in name_str:
            guide = url
        elif 'doi.org' in url:
            doi = url

    return guide, doi
    
def get_opensearch_hit(uuid) -> dict:
    """
    Query elasticsearch for the opensearch collections metadata
    """
    cli = Elasticsearch(hosts=['https://elasticsearch.ceda.ac.uk'])

    opensearch_resp = cli.search(
        index='opensearch-collections',
        body={
            "query":{
                "bool": {
                "must":[
                    {
                    "match":{
                        "collection_id":uuid
                    }
                    }
                ]
                }
            }
        })
    
    try:
        opensearch_hit = opensearch_resp['hits']['hits'][0]
    except IndexError or KeyError:
        opensearch_hit = {}
    
    return opensearch_hit.get('_source',{})

def backup_info(uuid) -> tuple:
    """
    Backup for start/end dates and ecv if not in collection.
    """

    url = f'https://opensearch-test.ceda.ac.uk/opensearch/description.xml?parentIdentifier=cci&uuid={uuid}'


    (rsp, error) = _fetch_url(url)
    if rsp is None:
        return None, None, {}
    root = ET.fromstring(rsp)

    facet_root = None
    for elem in root.findall('cci:Url', ns):
        if elem.attrib['rel'] == 'results' and elem.attrib['type'] == 'application/geo+json':
            facet_root = elem

    min_date = None
    max_date = None
    ecv = None

    if facet_root is not None:
        for elem in facet_root.findall('param:Parameter', ns):
            if elem.attrib['name'] in ['startDate'] and 'minInclusive' in elem.attrib:
                min_date = elem.attrib['minInclusive'].split('T')[0]
            elif elem.attrib['name'] in ['endDate'] and 'maxInclusive' in elem.attrib:
                max_date = elem.attrib['maxInclusive'].split('T')[0]

            if elem.attrib['name'] in ['ecv']:
                for option in elem.findall('param:Option', ns):
                    ecv = option.attrib['label'].split(' (')[0]
    return min_date, max_date, ecv
                            

class BasicHTMLView(FormView):
    template_name = 'base.html'

    def get(self, request, uuid):
        """
        Fill context for the GET request"""

        resp = requests.get(f'https://catalogue.ceda.ac.uk/api/v2/observations.json?uuid={uuid}')
        try:
            moles_resp = resp.json()['results'][0]
        except IndexError:
            moles_resp = {}

        opensearch_hit = get_opensearch_hit(uuid)

        if opensearch_hit == {}:
            return render(request,"404.html")
        
        start, end, ecv = backup_info(uuid)

        guide, doi = get_user_guide(uuid)

        moles_resp['start_date'] = opensearch_hit.get('start_date','').split('T')[0] or start
        moles_resp['end_date']   = opensearch_hit.get('end_date','').split('T')[0] or end

        moles_resp['catalog_link'] = f'https://catalogue.ceda.ac.uk/uuid/{uuid}'
        moles_resp['catalog_size'] = format_mem(moles_resp['result_field']['volume'])
        moles_resp['num_files']    = moles_resp['result_field']['numberOfFiles']

        # Data Lineage - esa_desc
        moles_resp['related_docs'] = moles_resp['catalog_link'] + '/?jump=related-docs-anchor'
        if opensearch_hit.get('path',False):
            moles_resp['download']     = os.path.join('https://data.cci.ceda.ac.uk/thredds/catalog',opensearch_hit.get('path').replace('/neodc/',''),'catalog.html')
            moles_resp['ftp_download'] = 'ftp://anon-ftp.ceda.ac.uk' + opensearch_hit.get('path')
        moles_resp['user_guide']   = guide
        moles_resp['data_lineage'] = moles_resp.pop('dataLineage',None)
        moles_resp['ecv']          = ecv

        #moles_resp['doi']     = doi.replace('http://','').replace('https://','') or None
        #moles_resp['doi_url'] = doi or None

        return render(request, "base.html", moles_resp)