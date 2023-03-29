from django.shortcuts import render
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import login as log_in
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction
from MainApp.models import Issues
from datetime import datetime
import json
import re
from django.views.decorators.csrf import csrf_exempt
from .utils import Syserror
UserModel = get_user_model()
ISSUE_TYPE_CHOICES = ['Printer', 'Network',
                      'Computer', 'Software', 'Email', 'Other']
ORG_CHOICES = ['Nsl', 'Mecon', 'Other']
DEG_CHOICES = ['Tco', 'Field Attendant', 'Junior Assistant', 'Junior Officer', 'Junior Manager', 'Executive Trainee',
               'Assistant Manager', 'Deputy Manager', 'Manager', 'Senior Manager', 'Agm', 'Dgm', 'Gm', 'Cgm', 'Ed']
LOC_CHOICES = ['Rmhs_Aso Building',
               'Coke Oven_Cdcp Boiler_By Product_Aso Building',
               'Sinter Plant_Aso Building',
               'Power & Blowing Station (Pbs)_Blast Furnace Aso Building',
               'Sms_Oxygen_Aso Building',
               'Thin Slab Caster & Hot Strip Mill(Tsc&Hsm)_Central R&Cl-Aso Building',
               'Cmos_Aso Building',
               'Old Project Office A-Block',
               'Old Project Office B-Block',
               'Old Project Office C-Block',
               'D-Block',
               'E-Block',
               'Mrss',
               'Fire Station',
               'Telecom',
               'Sinter Plant Admin Building (Pkg-04)',
               'Blast Furnace Admin Building (Pkg-05)',
               'Ldcp Admin Building (Pkg-08)',
               'Sms Admin Building (Pkg-06)',
               'Tsc&Hsm Admin Building (Pkg-07)',
               'Oxygen Plant Admin Building (Pkg-09)',
               'Coke Oven Admin Building (Pkg-02)',
               'By Product Admin Building (Pkg-03)',
               'Rmhs Admin Building (Pkg-01)',
               'Pbs Admin Building (Pkg-10)']


def HomeView(request):  # sourcery skip: last-if-guard
    return render(request, 'MainApp/index.html')


def RaiseTicketView(request):  # sourcery skip: last-if-guard
    return render(request, 'MainApp/ticket_raise.html')


@csrf_exempt
def raised_issue(request):
    if request.method != 'POST':
        resp_data = {"success": False, "message": "Required POST Method"}
        return JsonResponse(resp_data)
    try:
        data = json.loads(request.body)
        email = data.get("email", None)
        name = data.get("name", None)
        phone = data.get("phone", None)
        organization = data.get("organization", None)
        designation = data.get("designation", None)
        issue_type = data.get("issue_type", None)
        location = data.get("location", None)
        description = data.get("description", None)
        if not all([name, phone, organization, designation, issue_type, location, description]):
            resp_data = {"success": False, "message": "Required All Field"}
            return JsonResponse(resp_data)
        if not phone.isdigit():
            resp_data = {"success": False,
                         "message": "Phone number must be contains only digits"}
            return JsonResponse(resp_data)
        if len(phone) != 10:
            resp_data = {"success": False,
                         "message": "Phone nummber should be 10 digits"}
            return JsonResponse(resp_data)
        if email:
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                resp_data = {"success": False, "message": "Invalid email"}
                return JsonResponse(resp_data)
        if designation not in DEG_CHOICES:
            resp_data = {"success": False, "message": "Invalid Designation"}
            return JsonResponse(resp_data)
        if organization not in ORG_CHOICES:
            resp_data = {"success": False, "message": "Invalid Organization"}
            return JsonResponse(resp_data)
        if location not in LOC_CHOICES:
            resp_data = {"success": False, "message": "Invalid Location"}
            return JsonResponse(resp_data)
        if issue_type not in ISSUE_TYPE_CHOICES:
            resp_data = {"success": False, "message": "Invalid issue type"}
            return JsonResponse(resp_data)
        with transaction.atomic():
            issue = Issues.objects.create(
                emp_name=name, emp_email=email, emp_phone=phone, emp_organization=organization,
                emp_designation=designation, location=location, issue_type=issue_type,
                description=description, issue_date=datetime.now())
            resp_data = {"success": True, "message": "Issue raised successfully",
                         "ticket_number": issue.ticket_no}
            return JsonResponse(resp_data)

    except Exception as e:
        Syserror(e)
        resp_data = {"success": False, "message": f"{e}"}
        return JsonResponse(resp_data)


def TicketStatusView(request):  # sourcery skip: last-if-guard
    issue = None
    if ticket_number := request.GET.get("ticket_number", ''):
        if issueCheck := Issues.objects.filter(ticket_no=ticket_number):
            issue = issueCheck.first()
        else:
            messages.error(
                request, "Issue not found! Please enter a valid ticket no.")
    return render(request, 'MainApp/ticket_status.html', {'issue': issue, 'ticket_number': ticket_number})


def loginView(request):  # sourcery skip: last-if-guard
    if request.method == "POST":
        try:
            email = request.POST.get("email", None)
            password = request.POST.get("password", None)

            if not email:
                messages.error(request, "Required email or phone")
                return HttpResponseRedirect(reverse('login'))
            if not password:
                messages.error(request, "Required Password")
                return HttpResponseRedirect(reverse('login'))
            if not UserModel.objects.filter(Q(email=email) | Q(username=email)).exists():
                messages.error(request, "Email of username not found!")
                return HttpResponseRedirect(reverse('login'))
            user = UserModel.objects.get(Q(email=email) | Q(username=email))
            if user.check_password(password):
                log_in(request, user)
                return HttpResponseRedirect(reverse('dashboard'))
            else:
                messages.error(request, "Invalid Password")
                return HttpResponseRedirect(reverse('login'))
        except Exception as e:
            messages.error(request, f"Server Error: {e}")
            return HttpResponseRedirect(reverse('login'))
    else:
        return render(request, 'MainApp/login.html')
