from django.db import models


class DashboardAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("view_business_dashboard", "Can view business dashboard and export reports")]
