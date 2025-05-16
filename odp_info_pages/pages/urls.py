from django.contrib import admin
from django.urls import path
from .views import FrontPage, BasicHTMLView, BasicJSONView

urlpatterns = [
    path('',FrontPage.as_view()),
    path('<str:uuid>/', BasicHTMLView.as_view()),
    path('json/<str:uuid>/', BasicJSONView.as_view()),
]