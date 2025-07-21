from django.views import View
from django.views.generic import FormView
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.conf import settings

import requests
import xmltodict
from elasticsearch import Elasticsearch
from django.shortcuts import redirect

class FrontPage(View):
    template_name = 'base.html'

    def get(self, request):
        return render(request, '404.html',settings.DEFAULT_SHEETS)

class PrivacyRedirect(View):

    def get(self, request):
        return redirect('https://climate.esa.int/privacy')