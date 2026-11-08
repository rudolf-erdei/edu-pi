"""Setup, login and logout for the Settings PIN gate."""

import time

from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .settings_auth import (
    SESSION_KEY,
    claim_pin,
    clear_failures,
    is_locked_out,
    is_settings_authenticated,
    pin_is_configured,
    record_failure,
    safe_next,
    verify_pin,
)


class SettingsPinForm(forms.Form):
    """A 4–8 digit PIN."""

    pin = forms.CharField(
        label=_("PIN"),
        min_length=4,
        max_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "input input-bordered w-full",
                "inputmode": "numeric",
                "autocomplete": "off",
                "autofocus": True,
            }
        ),
        help_text=_("4–8 digits."),
    )

    def clean_pin(self):
        pin = self.cleaned_data["pin"]
        if not pin.isdigit():
            raise forms.ValidationError(_("The PIN must be digits only."))
        return pin


class SettingsPinSetupForm(SettingsPinForm):
    """The same PIN twice, so a typo cannot lock the device."""

    confirm = forms.CharField(
        label=_("Confirm PIN"),
        min_length=4,
        max_length=8,
        widget=forms.PasswordInput(
            attrs={
                "class": "input input-bordered w-full",
                "inputmode": "numeric",
                "autocomplete": "off",
            }
        ),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("pin") and cleaned.get("pin") != cleaned.get("confirm"):
            raise forms.ValidationError(_("The two PINs do not match."))
        return cleaned


def settings_setup(request):
    """First-run: choose the device PIN."""
    if pin_is_configured():
        return redirect("settings_login")

    next_url = safe_next(request, request.POST.get("next") or request.GET.get("next"))

    if request.method == "POST":
        form = SettingsPinSetupForm(request.POST)
        if form.is_valid():
            if not claim_pin(form.cleaned_data["pin"]):
                # Another client chose the PIN between the check and the
                # write. Their PIN stands; this one goes to login.
                return redirect("settings_login")
            request.session[SESSION_KEY] = time.time()
            messages.success(request, _("Settings PIN set."))
            return redirect(next_url)
        messages.error(request, _("Please correct the errors below."))
    else:
        form = SettingsPinSetupForm()

    return render(
        request,
        "settings/setup.html",
        {"title": _("Set a settings PIN"), "form": form, "next": next_url},
    )


def settings_login(request):
    """Ask for the PIN and, on success, open the requested page."""
    if not pin_is_configured():
        return redirect("settings_setup")
    if is_settings_authenticated(request):
        return redirect(safe_next(request, request.GET.get("next")))

    next_url = safe_next(request, request.POST.get("next") or request.GET.get("next"))
    form = SettingsPinForm(request.POST or None)

    if request.method == "POST":
        if is_locked_out(request):
            messages.error(
                request,
                _("Too many incorrect PINs. Try again in a few minutes."),
            )
        elif form.is_valid() and verify_pin(form.cleaned_data["pin"]):
            clear_failures(request)
            request.session[SESSION_KEY] = time.time()
            return redirect(next_url)
        else:
            record_failure(request)
            messages.error(request, _("Incorrect PIN."))

    return render(
        request,
        "settings/login.html",
        {"title": _("Settings are locked"), "form": form, "next": next_url},
    )


@require_POST
def settings_logout(request):
    """Forget the settings session, leaving the Django admin session alone."""
    request.session.pop(SESSION_KEY, None)
    messages.success(request, _("Signed out of Settings."))
    return redirect("home")
