from django.db import models
from django.utils.translation import gettext_lazy as _
from .utils import getId, generate_ticket_no, convert_hour


ISSUE_TYPE_CHOICES = [
    ('Printer', "PRINTER"),
    ('Network', "NETWORK"),
    ('Computer', "COMPUTER"),
    ('Software', "SOFTWARE"),
    ('Email', "EMAIL"),
    ('Other', "OTHER")
]

COMPLAINT_STATUS_CHOICES = [
    ('Unassigned', "UNASSIGNED"),
    ('Assigned', "ASSIGNED"),
    ('Rejected', "REJECTED"),
    ('Completed', "COMPLETED")
]

ORG_TYPE_CHOICES = [
    ('Nsl', "NSL"),
    ('Mecon', "MECON"),
    ('Other', "OTHER")
]

DEG_TYPE_CHOICES = [
    ('Tco', "TCO"),
    ('Field Attendant', "FIELD ATTENDANT"),
    ('Junior Assistant', "JUNIOR ASSISTANT"),
    ('Junior Officer', "JUNIOR OFFICER"),
    ('Junior Manager', "JUNIOR MANAGER"),
    ('Executive Trainee', "EXECUTIVE TRAINEE"),
    ('Assistant Manager', "ASSISTANT MANAGER"),
    ('Deputy Manager', "DEPUTY MANAGER"),
    ('Manager', "MANAGER"),
    ('Senior Manager', "SENIOR MANAGER"),
    ('Agm', "AGM"),
    ('Dgm', "DGM"),
    ('Gm', "GM"),
    ('Cgm', "CGM"),
    ('Ed', "ED")
]

LOC_TYPE_CHOICES = [
    ('Rmhs_Aso Building', "RMHS_ASO BUILDING"),
    ('Coke Oven_Cdcp Boiler_By Product_Aso Building', "COKE OVEN_CDCP BOILER_BY PRODUCT_ASO BUILDING"),
    ('Sinter Plant_Aso Building', "SINTER PLANT_ASO BUILDING"),
    ('Power & Blowing Station (Pbs)_Blast Furnace Aso Building', "POWER & BLOWING STATION (PBS)_BLAST FURNACE ASO BUILDING"),
    ('Sms_Oxygen_Aso Building', "SMS_OXYGEN_ASO BUILDING"),
    ('Thin Slab Caster & Hot Strip Mill(Tsc&Hsm)_Central R&Cl-Aso Building', "THIN SLAB CASTER & HOT STRIP MILL(TSC&HSM)_CENTRAL R&CL-ASO BUILDING"),
    ('Cmos_Aso Building', "CMOS_ASO BUILDING"),
    ('Old Project Office A-Block', "OLD PROJECT OFFICE A-BLOCK"),
    ('Old Project Office B-Block', "OLD PROJECT OFFICE B-BLOCK"),
    ('Old Project Office C-Block', "OLD PROJECT OFFICE -C-BLOCK"),
    ('D-Block', "D-BLOCK"),
    ('E-Block', "E-BLOCK"),
    ('Mrss', "MRSS"),
    ('Fire Station', "FIRE STATION"),
    ('Telecom', "TELECOM"),
    ('Sinter Plant Admin Building (Pkg-04)', "SINTER PLANT ADMIN BUILDING (PKG-04)"),
    ('Blast Furnace Admin Building (Pkg-05)', "BLAST FURNACE ADMIN BUILDING (PKG-05)"),
    ('Ldcp Admin Building (Pkg-08)', "LDCP ADMIN BUILDING (PKG-08)"),
    ('Sms Admin Building (Pkg-06)', "SMS ADMIN BUILDING (PKG-06)"),
    ('Tsc&Hsm Admin Building (Pkg-07)', "TSC&HSM ADMIN BUILDING (PKG-07)"),
    ('Oxygen Plant Admin Building (Pkg-09)', "OXYGEN PLANT ADMIN BUILDING (PKG-09)"),
    ('Coke Oven Admin Building (Pkg-02)', "COKE OVEN ADMIN BUILDING (PKG-02)"),
    ('By Product Admin Building (Pkg-03)', "BY PRODUCT ADMIN BUILDING (PKG-03)"),
    ('Rmhs Admin Building (Pkg-01)', "RMHS ADMIN BUILDING (PKG-01)"),
    ('Pbs Admin Building (Pkg-10)', "PBS ADMIN BUILDING (PKG-10)")
    
]

class Issues(models.Model):
    id = models.CharField(editable=False, primary_key=True, max_length=255)
    issue_type = models.CharField(
        default=ISSUE_TYPE_CHOICES[0][0], choices=ISSUE_TYPE_CHOICES, max_length=15)
    status = models.CharField(
        default=COMPLAINT_STATUS_CHOICES[0][0], choices=COMPLAINT_STATUS_CHOICES, max_length=15)
    ticket_no = models.CharField(max_length=50)
    emp_email = models.EmailField(_('email address'), null=True)
    emp_name = models.CharField(max_length=50)
    emp_phone = models.CharField(max_length=10)
    emp_designation = models.CharField(
        default=DEG_TYPE_CHOICES[0][0], choices=DEG_TYPE_CHOICES, max_length=20)
    emp_organization = models.CharField(
        default=ORG_TYPE_CHOICES[0][0], choices=ORG_TYPE_CHOICES, max_length=15)
    description = models.TextField()
    location = models.CharField(
        default=LOC_TYPE_CHOICES[0][0], choices=LOC_TYPE_CHOICES, max_length=80)
    assign_name = models.CharField(max_length=50, null=True)
    assign_phone = models.CharField(max_length=10, null=True)
    issue_date = models.DateTimeField()
    resolved_date = models.DateTimeField(null=True)
    assigned_date = models.DateTimeField(null=True)
    rejected_date = models.DateTimeField(null=True)
    rejected_reason = models.TextField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True)
    objects = models.Manager()

    @property
    def raised_assigned_hour(self):
        # your logic for due date
        total_hour = '0'
        if self.assigned_date:
            total_hour = convert_hour((self.assigned_date - self.created_at).total_seconds())
        return total_hour

    @property
    def assigned_resolved_hour(self):
        # your logic for due date
        total_hour = '0'
        if self.assigned_date and self.resolved_date:
            total_hour = convert_hour((self.resolved_date - self.assigned_date).total_seconds())
        return total_hour

    @property
    def assigned_rejected_hour(self):
        # your logic for due date
        total_hour = '0'
        if self.assigned_date and self.rejected_date:
            total_hour = convert_hour((self.rejected_date - self.assigned_date).total_seconds())
        return total_hour

    @property
    def raised_resolved_hour(self):
        # your logic for due date
        total_hour = '0'
        if self.resolved_date:
            total_hour = convert_hour((self.resolved_date - self.created_at).total_seconds())
        return total_hour

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = getId('user')
            while Issues.objects.filter(id=self.id).exists():
                self.id = getId('issue')
        if not self.ticket_no:
            total = Issues.objects.all().count()
            if total > 0:
                new_total = total + 1
                self.ticket_no = generate_ticket_no(str(new_total), 'NSLT')
                while Issues.objects.filter(ticket_no=self.ticket_no).exists():
                    new_total += 1
                    self.ticket_no = generate_ticket_no(str(new_total), 'NSLT')
            else:
                self.ticket_no = generate_ticket_no(None, 'NSLT')
        super(Issues, self).save()
