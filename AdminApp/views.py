from django.shortcuts import render
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth import logout as log_out
# Create your views here.
from django.db.models import Q, Count, F, Sum, Avg
from django.db import transaction
from datetime import datetime, timedelta
from MainApp.models import Issues
from django.template.loader import render_to_string, get_template
import json
from io import BytesIO
from xhtml2pdf import pisa
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.serializers.json import DjangoJSONEncoder
from django.core.serializers import serialize
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 10


class LazyEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime("%m/%d/%Y, %H:%M %a")
        return super().default(obj)


def logoutView(request):
    log_out(request)
    return HttpResponseRedirect(reverse("login"))


def dashboardView(request):
    today = datetime.now().date()
    issues = Issues.objects.aggregate(
        unassigned_issue=(Count('id', filter=Q(status="Unassigned"))),
        assigned_issue=(Count('id', filter=Q(status="Assigned"))),
        completed_issue=(Count('id', filter=Q(status="Completed"))),
        rejected_issue=(Count('id', filter=Q(status="Rejected"))),
        today_raised=(Count('id', filter=Q(
            status="Unassigned", issue_date__date=today))),
        today_resolved=(Count('id', filter=Q(
            status="Completed", resolved_date__date=today))),
        computer_issue=(Count('id', filter=Q(issue_type="Computer"))),
        email_issue=(Count('id', filter=Q(issue_type="Email"))),
        network_issue=(Count('id', filter=Q(issue_type="Network"))),
        printer_issue=(Count('id', filter=Q(issue_type="Printer"))),
        software_issue=(Count('id', filter=Q(issue_type="Software"))),
        other_issue=(Count('id', filter=Q(issue_type="Other"))),
    )
    return render(request, 'AdminApp/dashboard.html', issues)


def manageIssuesView(request):
    if request.method == "POST":
        try:
            issue_id = request.POST.get("issue_id", None)
            assign_name = request.POST.get("assign_name", None)
            assign_phone = request.POST.get("assign_phone", None)
            if not issue_id:
                messages.error(request, "Required ticket id")
                return HttpResponseRedirect(reverse('manage_issues'))
            if not assign_name:
                messages.error(request, "Required service engineer name")
                return HttpResponseRedirect(reverse('manage_issues'))
            if not assign_phone:
                messages.error(request, "Required service engineer phone")
                return HttpResponseRedirect(reverse('manage_issues'))
            if not assign_phone.isdigit():
                resp_data = {
                    "success": False, "message": "Phone number must be contains only digits"}
                return JsonResponse(resp_data)
            if len(assign_phone) != 10:
                resp_data = {"success": False,
                             "message": "Phone nummber should be 10 digits"}
                return JsonResponse(resp_data)
            with transaction.atomic():
                issue = Issues.objects.get(id=issue_id)
                if issue.status == "Completed":
                    messages.error(
                        request, "Ticket already completed! Service engineer can't be assign")
                    return HttpResponseRedirect(reverse('manage_issues'))
                if issue.status == "Rejected":
                    messages.error(
                        request, "Ticket already rejected! Service engineer can't be assign")
                    return HttpResponseRedirect(reverse('manage_issues'))
                issue.assign_name = assign_name
                issue.assign_phone = assign_phone
                if issue.status == "Unassigned":
                    issue.status = "Assigned"
                    issue.assigned_date = datetime.now()
                issue.save()
                messages.success(
                    request, "Service engineer assigned successfully")
                return HttpResponseRedirect(reverse('manage_issues'))
        except Exception as e:
            messages.error(request, f"Server Error: {e}")
            return HttpResponseRedirect(reverse('manage_issues'))
    else:
        f = Q()
        if from_date := request.GET.get('from_date', ''):
            from_date = datetime.strptime(from_date, '%Y-%m-%d')
            f &= Q(created_at__date__gte=from_date)
        if to_date := request.GET.get('to_date', ''):
            to_date = datetime.strptime(to_date, '%Y-%m-%d')
            f &= Q(created_at__date__lte=to_date)
        if ticket_status := request.GET.get('ticket_status', ''):
            f &= Q(status=ticket_status)
            if action_date := request.GET.get('action_date', ''):
                action_date = datetime.strptime(action_date, '%Y-%m-%d').date()
                if ticket_status == "Completed":
                    f &= Q(resolved_date__date=action_date)
                elif ticket_status == "Unassigned":
                    f &= Q(created_at__date=action_date)

        if ticket_type := request.GET.get('ticket_type', ''):
            f &= Q(issue_type=ticket_type)
        ob_list = ['ticket_no', 'created_at', 'emp_name', 'assign_name', 'issue_type', 'status', '-ticket_no',
                   '-created_at', '-emp_name', '-assign_name', '-issue_type', '-status']
        order_by = request.GET.get('order_by', None)
        if order_by and order_by in ob_list:
            pass
        else:
            order_by = '-ticket_no'
        if query := request.GET.get('query', ''):
            f &= Q(Q(ticket_no__icontains=query) |
                   Q(location__icontains=query) |
                   Q(emp_organization__icontains=query) |
                   Q(assign_name__icontains=query) |
                   Q(assign_phone__icontains=query) |
                   Q(emp_name__icontains=query) |
                   Q(emp_phone__icontains=query))
        issues_list = Issues.objects.filter(f).order_by(order_by)
        page = request.GET.get('page', DEFAULT_PAGE)
        paginator = Paginator(issues_list, DEFAULT_PER_PAGE)
        try:
            issues = paginator.page(page)
        except PageNotAnInteger:
            issues = paginator.page(DEFAULT_PAGE)
        except EmptyPage:
            issues = paginator.page(paginator.num_pages)
        context = {
            "issues": issues,
            "from_date": from_date,
            "to_date": to_date,
            "ticket_status": ticket_status,
            "ticket_type": ticket_type,
            "query": query,
            "order_by": order_by,
            "page": page
        }
        return render(request, 'AdminApp/manage_issues.html', context)


def updateIssueStatusView(request):  # sourcery skip: last-if-guard
    if request.method == "POST":
        try:
            issue_id = request.POST.get("issue_id", None)
            status = request.POST.get("status", None)
            if not issue_id:
                messages.error(request, "Required issue id")
                return HttpResponseRedirect(reverse('manage_issues'))
            if not status:
                messages.error(request, "Required issue status")
                return HttpResponseRedirect(reverse('manage_issues'))
            with transaction.atomic():
                issue = Issues.objects.get(id=issue_id)
                if issue.assign_name == issue.assign_phone == None:
                    messages.error(
                        request, "To update ticket status first assign a service engineer.")
                    return HttpResponseRedirect(reverse('manage_issues'))
                if issue.status in ['Completed', "Rejected"]:
                    messages.error(
                        request, f"Failed to update. Ticket was already {issue.status} !")
                    return HttpResponseRedirect(reverse('manage_issues'))

                if issue.status in ["Rejected", "Completed"]:
                    messages.error(
                        request, f"Tickets has been already {status} !")
                    return HttpResponseRedirect(reverse('manage_issues'))

                if issue.status in ["Assigned", "Rejected"] and status == "Completed":
                    issue.status = "Completed"
                    issue.resolved_date = datetime.now()
                    issue.rejected_date = None
                    issue.rejected_reason = None

                elif issue.status == "Assigned" and status == "Rejected":
                    if rejected_reason := request.POST.get("rejected_reason", None):
                        issue.status = "Rejected"
                        issue.rejected_date = datetime.now()
                        issue.rejected_reason = rejected_reason
                        issue.resolved_date = None
                    else:
                        messages.error(request, "Required rejected reason.")
                        return HttpResponseRedirect(reverse('manage_issues'))

                elif issue.status == "Rejected" and status == "Rejected":
                    if rejected_reason := request.POST.get("rejected_reason", None):
                        issue.rejected_reason = rejected_reason
                    else:
                        messages.error(request, "Required rejected reason.")
                        return HttpResponseRedirect(reverse('manage_issues'))

                elif issue.status == "Rejected" and status == "Assigned":
                    print("Reject", request.POST)
                    issue.status = "Assigned"
                    issue.resolved_date = None
                    issue.rejected_date = None
                    issue.rejected_reason = None
                issue.save()
                messages.success(request, "Ticket status updated successfully")
                return HttpResponseRedirect(reverse('manage_issues'))
        except Exception as e:
            messages.error(request, f"Server Error: {e}")
            return HttpResponseRedirect(reverse('manage_issues'))
    else:
        messages.error(request, "Invalid Request! Require Post Method")
        return HttpResponseRedirect(reverse('manage_issues'))


def ticketReportView(request):
    if request.method == "POST":
        messages.error(request, "Invalid Method POST")
        return HttpResponseRedirect(reverse('tickets_report'))
    else:
        f = Q()
        if from_date := request.GET.get('from_date', ''):
            from_date = datetime.strptime(from_date, '%Y-%m-%d')
            f &= Q(created_at__date__gte=from_date)
        if to_date := request.GET.get('to_date', ''):
            to_date = datetime.strptime(to_date, '%Y-%m-%d')
            f &= Q(created_at__date__lte=to_date)
        if ticket_type := request.GET.get('ticket_type', ''):
            f &= Q(issue_type=ticket_type)
        if ticket_status := request.GET.get('ticket_status', ''):
            f &= Q(status=ticket_status)
        ob_list = ['ticket_no', 'created_at', 'emp_name', 'assign_name', 'issue_type', 'status', '-ticket_no',
                   '-created_at', '-emp_name', '-assign_name', '-issue_type', '-status']
        order_by = request.GET.get('order_by', None)
        if order_by and order_by in ob_list:
            pass
        else:
            order_by = '-created_at'
        if query := request.GET.get('query', ''):
            f &= Q(Q(ticket_no__icontains=query) |
                   Q(location__icontains=query) |
                   Q(emp_organization__icontains=query) |
                   Q(assign_name__icontains=query) |
                   Q(assign_phone__icontains=query) |
                   Q(emp_name__icontains=query) |
                   Q(emp_phone__icontains=query))
        issues_list = Issues.objects.filter(f).order_by(order_by)
        page = request.GET.get('page', DEFAULT_PAGE)
        paginator = Paginator(issues_list, DEFAULT_PER_PAGE)
        try:
            issues = paginator.page(page)
        except PageNotAnInteger:
            issues = paginator.page(DEFAULT_PAGE)
        except EmptyPage:
            issues = paginator.page(paginator.num_pages)
        josn_issue = serialize('json', issues_list, cls=LazyEncoder)
        context = {
            "issues": issues,
            "from_date": from_date,
            "to_date": to_date,
            "ticket_type": ticket_type,
            "ticket_status": ticket_status,
            "query": query,
            "order_by": order_by,
            "page": page,
            "issues_list_json": json.dumps(josn_issue)
        }
        return render(request, 'AdminApp/issues_report.html', context)


@csrf_exempt
def issueAnalyticsView(request):
    if request.method != "POST":
        return JsonResponse({'success': False, 'message': "required post method"})
    try:
        from_date = (datetime.now() - timedelta(days=6)).date()
        to_date = datetime.now().date()
        date_list = [from_date + timedelta(days=x)
                     for x in range((to_date - from_date).days + 1)]
        issue_graph = Issues.objects.filter(created_at__date__gte=from_date, created_at__date__lte=to_date).values(
            'created_at__date').annotate(
            unassigned_issue=(Count('id', filter=Q(status="Unassigned"))),
            assigned_issue=(Count('id', filter=Q(status="Assigned"))),
            completed_issue=(Count('id', filter=Q(status="Completed"))),
            rejected_issue=(Count('id', filter=Q(status="Rejected"))),

            computer_issue=(Count('id', filter=Q(issue_type="Computer"))),
            email_issue=(Count('id', filter=Q(issue_type="Email"))),
            network_issue=(Count('id', filter=Q(issue_type="Network"))),
            printer_issue=(Count('id', filter=Q(issue_type="Printer"))),
            software_issue=(Count('id', filter=Q(issue_type="Software"))),
            other_issue=(Count('id', filter=Q(issue_type="Other"))),

        )
        labels, unassigned, assigned, completed, rejected, computer, email, network, printer, software, other = ([
        ] for _ in range(11))

        def finddata(date):
            isu = list(filter(None, [
                value if value['created_at__date'] == date else {} for value in issue_graph]))
            if isu:
                unassigned.append(isu[0]['unassigned_issue'])
                assigned.append(isu[0]['assigned_issue'])
                completed.append(isu[0]['completed_issue'])
                rejected.append(isu[0]['rejected_issue'])

                computer.append(isu[0]['computer_issue'])
                email.append(isu[0]['email_issue'])
                network.append(isu[0]['network_issue'])
                printer.append(isu[0]['printer_issue'])
                software.append(isu[0]['software_issue'])
                other.append(isu[0]['other_issue'])
            else:
                unassigned.append(0)
                assigned.append(0)
                completed.append(0)
                rejected.append(0)

                computer.append(0)
                email.append(0)
                network.append(0)
                printer.append(0)
                software.append(0)
                other.append(0)
            labels.append(date.strftime('%d-%b'))
            return None

        list(map(finddata, date_list))

        issues_status_series = [
            {'name': 'Unassigned', 'data': unassigned},
            {'name': 'Assigned', 'data': assigned},
            {'name': 'Completed', 'data': completed},
            {'name': 'Rejected', 'data': rejected}
        ]
        issues_type_series = [
            {'name': 'Computer', 'data': computer},
            {'name': 'Email', 'data': email},
            {'name': 'Network', 'data': network},
            {'name': 'Printer', 'data': printer},
            {'name': 'Software', 'data': software},
            {'name': 'Other', 'data': other}
        ]
        data = {'labels': labels,
                'issues_status_series': issues_status_series,
                'issues_type_series': issues_type_series
                }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': e})


@csrf_exempt
def issueAverageTimeAnalyticsView(request):
    if request.method != "POST":
        return JsonResponse({'success': False, 'message': "required post method"})
    try:
        issue_graph = Issues.objects.aggregate(
            # raised_resolved
            rr_computer=(Avg((F('resolved_date') - F('created_at')),
                             filter=Q(issue_type="Computer", status="Completed", resolved_date__isnull=False))),
            rr_email=(Avg((F('resolved_date') - F('created_at')),
                          filter=Q(issue_type="Email", status="Completed", resolved_date__isnull=False))),
            rr_network=(Avg((F('resolved_date') - F('created_at')),
                            filter=Q(issue_type="Network", status="Completed", resolved_date__isnull=False))),
            rr_printer=(Avg((F('resolved_date') - F('created_at')),
                            filter=Q(issue_type="Printer", status="Completed", resolved_date__isnull=False))),
            rr_software=(Avg((F('resolved_date') - F('created_at')),
                             filter=Q(issue_type="Software", status="Completed", resolved_date__isnull=False))),
            rr_other=(Avg((F('resolved_date') - F('created_at')),
                          filter=Q(issue_type="Other", status="Completed", resolved_date__isnull=False))),
            # raised_assigned

            ra_computer=(Avg((F('assigned_date') - F('created_at')),
                             filter=Q(issue_type="Computer", status="Assigned", assigned_date__isnull=False))),
            ra_email=(Avg((F('assigned_date') - F('created_at')),
                          filter=Q(issue_type="Email", status="Assigned", assigned_date__isnull=False))),
            ra_network=(Avg((F('assigned_date') - F('created_at')),
                            filter=Q(issue_type="Network", status="Assigned", assigned_date__isnull=False))),
            ra_printer=(Avg((F('assigned_date') - F('created_at')),
                            filter=Q(issue_type="Printer", status="Assigned", assigned_date__isnull=False))),
            ra_software=(Avg((F('assigned_date') - F('created_at')),
                             filter=Q(issue_type="Software", status="Assigned", assigned_date__isnull=False))),
            ra_other=(Avg((F('assigned_date') - F('created_at')),
                          filter=Q(issue_type="Other", status="Assigned", assigned_date__isnull=False))),

            # assigned_resolved

            ar_computer=(Avg((F('resolved_date') - F('assigned_date')),
                             filter=Q(issue_type="Computer", status="Completed", resolved_date__isnull=False))),
            ar_email=(Avg((F('resolved_date') - F('assigned_date')),
                          filter=Q(issue_type="Email", status="Completed", resolved_date__isnull=False))),
            ar_network=(Avg((F('resolved_date') - F('assigned_date')),
                            filter=Q(issue_type="Network", status="Completed", resolved_date__isnull=False))),
            ar_printer=(Avg((F('resolved_date') - F('assigned_date')),
                            filter=Q(issue_type="Printer", status="Completed", resolved_date__isnull=False))),
            ar_software=(Avg((F('resolved_date') - F('assigned_date')),
                             filter=Q(issue_type="Software", status="Completed", resolved_date__isnull=False))),
            ar_other=(Avg((F('resolved_date') - F('assigned_date')),
                          filter=Q(issue_type="Other", status="Completed", resolved_date__isnull=False))),

            # assigned_rejected

            arj_computer=(Avg((F('rejected_date') - F('assigned_date')),
                              filter=Q(issue_type="Computer", status="Rejected", rejected_date__isnull=False))),
            arj_email=(Avg((F('rejected_date') - F('assigned_date')),
                           filter=Q(issue_type="Email", status="Rejected", rejected_date__isnull=False))),
            arj_network=(Avg((F('rejected_date') - F('assigned_date')),
                             filter=Q(issue_type="Network", status="Rejected", rejected_date__isnull=False))),
            arj_printer=(Avg((F('rejected_date') - F('assigned_date')),
                             filter=Q(issue_type="Printer", status="Rejected", rejected_date__isnull=False))),
            arj_software=(Avg((F('rejected_date') - F('assigned_date')),
                              filter=Q(issue_type="Software", status="Rejected", rejected_date__isnull=False))),
            arj_other=(Avg((F('rejected_date') - F('assigned_date')),
                           filter=Q(issue_type="Other", status="Rejected", rejected_date__isnull=False))),

        )
        print(issue_graph)
        rr_computer = int(issue_graph['rr_computer'].total_seconds() / 3600) if issue_graph['rr_computer'] else 0
        rr_email = int(issue_graph['rr_email'].total_seconds() / 3600) if issue_graph['rr_email'] else 0
        rr_network = int(issue_graph['rr_network'].total_seconds() / 3600) if issue_graph['rr_network'] else 0
        rr_printer = int(issue_graph['rr_printer'].total_seconds() / 3600) if issue_graph['rr_printer'] else 0
        rr_software = int(issue_graph['rr_computer'].total_seconds() / 3600) if issue_graph['rr_software'] else 0
        rr_other = int(issue_graph['rr_other'].total_seconds() / 3600) if issue_graph['rr_other'] else 0

        ra_computer = int(issue_graph['ra_computer'].total_seconds() / 3600) if issue_graph['ra_computer'] else 0
        ra_email = int(issue_graph['ra_email'].total_seconds() / 3600) if issue_graph['ra_email'] else 0
        ra_network = int(issue_graph['ra_network'].total_seconds() / 3600) if issue_graph['ra_network'] else 0
        ra_printer = int(issue_graph['ra_printer'].total_seconds() / 3600) if issue_graph['ra_printer'] else 0
        ra_software = int(issue_graph['ra_computer'].total_seconds() / 3600) if issue_graph['ra_software'] else 0
        ra_other = int(issue_graph['ra_other'].total_seconds() / 3600) if issue_graph['ra_other'] else 0

        ar_computer = int(issue_graph['ar_computer'].total_seconds() / 3600) if issue_graph['ar_computer'] else 0
        ar_email = int(issue_graph['ar_email'].total_seconds() / 3600) if issue_graph['ar_email'] else 0
        ar_network = int(issue_graph['ar_network'].total_seconds() / 3600) if issue_graph['ar_network'] else 0
        ar_printer = int(issue_graph['ar_printer'].total_seconds() / 3600) if issue_graph['ar_printer'] else 0
        ar_software = int(issue_graph['ar_computer'].total_seconds() / 3600) if issue_graph['ar_software'] else 0
        ar_other = int(issue_graph['ar_other'].total_seconds() / 3600) if issue_graph['ar_other'] else 0

        arj_computer = int(issue_graph['arj_computer'].total_seconds() / 3600) if issue_graph['arj_computer'] else 0
        arj_email = int(issue_graph['arj_email'].total_seconds() / 3600) if issue_graph['arj_email'] else 0
        arj_network = int(issue_graph['arj_network'].total_seconds() / 3600) if issue_graph['arj_network'] else 0
        arj_printer = int(issue_graph['arj_printer'].total_seconds() / 3600) if issue_graph['arj_printer'] else 0
        arj_software = int(issue_graph['arj_computer'].total_seconds() / 3600) if issue_graph['arj_software'] else 0
        arj_other = int(issue_graph['arj_other'].total_seconds() / 3600) if issue_graph['arj_other'] else 0

        labels = ['Computer', 'Email', 'Network', 'Printer', 'Software', 'Other']
        raised_resolved_series = [rr_computer, rr_email, rr_network, rr_printer, rr_software, rr_other]
        raised_assigned_series = [ra_computer, ra_email, ra_network, ra_printer, ra_software, ra_other]
        assigned_resolved_series = [ar_computer, ar_email, ar_network, ar_printer, ar_software, ar_other]
        assigned_rejected_series = [arj_computer, arj_email, arj_network, arj_printer, arj_software, arj_other]
        data = {'labels': labels,
                "series": [{
                    "name": 'Raised - Assigned',
                    "data": raised_assigned_series
                }, {
                    "name": 'Assigned - Resolved',
                    "data": assigned_resolved_series
                },
                    {
                        "name": 'Raised - Resolved',
                        "data": raised_resolved_series
                    },
                    {
                        "name": 'Assigned - Rejected',
                        "data": assigned_rejected_series
                    }]
                }
        return JsonResponse({'success': True, 'data': data})
    except Exception as e:
        return JsonResponse({'success': False, 'message': e})


def changeNameView(request):  # sourcery skip: last-if-guard
    if request.method == "POST":
        try:
            first_name = request.POST.get("first_name", None)
            last_name = request.POST.get("last_name", None)
            if not first_name:
                messages.error(request, "Required first name")
                return HttpResponseRedirect(reverse('manage_issues'))
            if not last_name:
                messages.error(request, "Required last name")
                return HttpResponseRedirect(reverse('manage_issues'))

            with transaction.atomic():
                user = request.user
                user.first_name = first_name
                user.last_name = last_name
                user.save()
                messages.success(request, "Name Changed successfullly")
                return HttpResponseRedirect(reverse('manage_issues'))
        except Exception as e:
            messages.error(request, f"Server Error: {e}")
            return HttpResponseRedirect(reverse('manage_issues'))
    else:
        messages.error(request, "Invalid Request! Require Post Method")
        return HttpResponseRedirect(reverse('manage_issues'))


def download_ticket_report(request, id):
    issue = Issues.objects.get(id=id)
    context = {'issue': issue, "host_name": request.build_absolute_uri('/')}
    template = get_template('AdminApp/report_pdf.html')
    html = template.render(context)
    response = HttpResponse(content_type='application/pdf')
    filename = f"nsl_ticker_report{issue.ticket_no}.pdf"
    response['Content-Disposition'] = f'filename={filename}'
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Failed to download template.', status=200)
    return response

def ticketReportAverateTimeView(request):
    if request.method == "POST":
        messages.error(request, "Invalid Method POST")
        return HttpResponseRedirect(reverse('tickets_report'))
    else:
        f = Q()
        filter_type = request.GET.get('filter_type', 'Raised_Assigned')
        ticket_type = request.GET.get('ticket_type', 'Computer')
        filter_type_list = ['Raised_Assigned', 'Assigned_Resolved', 'Raised_Resolved', 'Assigned_Rejected']
        ticket_type_list = ['Computer', 'Email', 'Network', 'Printer', 'Software', 'Other']
        if filter_type in filter_type_list and ticket_type in ticket_type_list:
            if filter_type == "Raised_Assigned":
                f &= Q(status="Assigned", assigned_date__isnull=False)
            elif filter_type == "Assigned_Resolved":
                f &= Q(status="Completed", resolved_date__isnull=False)
            elif filter_type == "Assigned_Rejected":
                f &= Q(status="Rejected", rejected_date__isnull=False)
            else:
                f &= Q(status="Completed", resolved_date__isnull=False)
            f &= Q(issue_type=ticket_type)
            issues_list = Issues.objects.filter(f).order_by('-created_at')
            page = request.GET.get('page', DEFAULT_PAGE)
            paginator = Paginator(issues_list, DEFAULT_PER_PAGE)
            try:
                issues = paginator.page(page)
            except PageNotAnInteger:
                issues = paginator.page(DEFAULT_PAGE)
            except EmptyPage:
                issues = paginator.page(paginator.num_pages)
            context = {
                "issues": issues,
                "filter_type": filter_type,
                "ticket_type": ticket_type
            }
            return render(request, 'AdminApp/issues_report_avg_time.html', context)
        else:
            messages.error(request, f"Check Valid Filter Filter Type: {filter_type}, Ticket Type : {ticket_type}")
            return HttpResponseRedirect(reverse('tickets_report'))

