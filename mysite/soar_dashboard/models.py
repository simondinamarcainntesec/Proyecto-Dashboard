from django.db import models

class IaSoar(models.Model):
    alarm_id        = models.TextField(primary_key=True)
    device          = models.TextField(blank=True, null=True)
    severity        = models.TextField(blank=True, null=True)
    srcip           = models.TextField(blank=True, null=True)
    dstip           = models.TextField(blank=True, null=True)
    srccountry      = models.TextField(blank=True, null=True)
    dstcountry      = models.TextField(blank=True, null=True)
    service         = models.TextField(blank=True, null=True)
    policyid        = models.TextField(blank=True, null=True)
    policyname      = models.TextField(blank=True, null=True)
    policyuuid      = models.TextField(blank=True, null=True)
    action          = models.TextField(blank=True, null=True)            # "action"
    security_action = models.TextField(blank=True, null=True)
    app             = models.TextField(blank=True, null=True)
    app_category    = models.TextField(blank=True, null=True)
    app_risk        = models.TextField(blank=True, null=True)
    app_action      = models.TextField(blank=True, null=True)
    app_control_list = models.TextField(blank=True, null=True)
    trandisp        = models.TextField(blank=True, null=True)
    proto           = models.TextField(blank=True, null=True)
    srcintf         = models.TextField(blank=True, null=True)
    dstintf         = models.TextField(blank=True, null=True)
    srcintfrole     = models.TextField(blank=True, null=True)
    dstintfrole     = models.TextField(blank=True, null=True)
    duration        = models.TextField(blank=True, null=True)
    sent            = models.TextField(blank=True, null=True)
    received        = models.TextField(blank=True, null=True)
    sent_packets    = models.TextField(blank=True, null=True)
    received_packets = models.TextField(blank=True, null=True)
    dstcity         = models.TextField(blank=True, null=True)
    dstregion       = models.TextField(blank=True, null=True)
    dstreputation   = models.TextField(blank=True, null=True)
    srcnatip        = models.TextField(blank=True, null=True)
    srcnatport      = models.TextField(blank=True, null=True)
    master_src_mac  = models.TextField(blank=True, null=True)
    src_mac         = models.TextField(blank=True, null=True)
    dst_mac         = models.TextField(blank=True, null=True)
    vwlid           = models.TextField(blank=True, null=True)
    vwlname         = models.TextField(blank=True, null=True)
    vwlquality      = models.TextField(blank=True, null=True)
    date            = models.TextField(blank=True, null=True)            # "date"
    time            = models.TextField(blank=True, null=True)            # "time"
    displayname     = models.TextField(blank=True, null=True)
    aotag           = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'agent"."ia_soar'
        # si en el futuro usas Django con soporte de esquema:
        # db_table = 'ia_soar'
        # db_table_schema = 'agent'
