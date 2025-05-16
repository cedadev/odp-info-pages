from django.views import View
from django.views.generic import FormView
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

import requests
import xmltodict
from elasticsearch import Elasticsearch

def format_mem(m: int):
    suffix = ['B','KB','MB','GB','TB','PB']
    index = 0

    while m > 1:
        m = m/1000
        index += 1
    m = f'{m*1000:.2f}'
    return f'{m} {suffix[index-1]}'

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

class BasicHTMLView(FormView):
    template_name = 'base.html'

    def get(self, request, uuid):

        resp = requests.get(f'https://catalogue.ceda.ac.uk/api/v2/observations.json?uuid={uuid}')
        try:
            moles_resp = resp.json()['results'][0]
        except IndexError:
            moles_resp = {}

        # Elasticsearch query
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

        if moles_resp == {} and opensearch_hit == {}:
            return render(request,"404.html")
        
        print(opensearch_hit)
        
        moles_resp['start_date'] = opensearch_hit['_source']['start_date'].split('T')[0]
        moles_resp['end_date'] = opensearch_hit['_source']['end_date'].split('T')[0]

        # Date time range (formatted to just days)
        # Number of files
        # Catalogue size
        # Link to MOLES - Dataset Information
        moles_resp['catalog_link'] = f'https://catalogue.ceda.ac.uk/uuid/{uuid}'
        moles_resp['catalog_size'] = format_mem(moles_resp['result_field']['volume'])
        moles_resp['num_files'] = moles_resp['result_field']['numberOfFiles']

        # Data Lineage - esa_desc
        moles_resp['related_docs'] = moles_resp['catalog_link'] + '/?jump=related-docs-anchor'
        moles_resp['download'] = 'https://data.ceda.ac.uk' + opensearch_hit['_source']['path']
        moles_resp['ftp_download'] = 'ftp://anon-ftp.ceda.ac.uk' + opensearch_hit['_source']['path']
        moles_resp['user_guide'] = f"https://data.ceda.ac.uk/neodc/esacci/{opensearch_hit['_source']['ecv'][0].lower()}/docs/"
        moles_resp['data_lineage'] = moles_resp.pop('dataLineage',None)
        moles_resp['ecv'] = opensearch_hit['_source']['ecv'][0].title()

        return render(request, "base.html", moles_resp)