from django import forms

class TenantLoginForm(forms.Form):
    tenant = forms.CharField(label="Empresa", max_length=255)
    username = forms.CharField(label="Usuario")
    password = forms.CharField(widget=forms.PasswordInput)
