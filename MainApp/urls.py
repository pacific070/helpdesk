from django.urls import path
from MainApp import views
urlpatterns = [
    path('helpdesk', views.HomeView, name="home"),
    path('raise_ticket', views.RaiseTicketView, name="raise_ticket"),
    path('ticket_status', views.TicketStatusView, name="ticket_status"),
    path('login', views.loginView, name="login"),
    path('raised_issue', views.raised_issue, name="raised_issue"),
]
