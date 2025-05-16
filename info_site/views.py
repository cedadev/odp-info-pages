from django.views import View
from django.views.generic import FormView
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

import requests
import xmltodict
from elasticsearch import Elasticsearch

class FrontPage(View):
    template_name = 'base.html'

    def get(self, request):
        return render(request, '404.html',{})
