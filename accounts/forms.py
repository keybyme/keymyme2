from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms

from vault.forms import TailwindFormMixin


class SignupForm(TailwindFormMixin, AllauthSignupForm):
    """Adds first/last name to allauth's stock signup form (email +
    password only by default) — used to greet the user and to give the
    admin something to recognize them by when approving the account in
    /admin. DefaultAccountAdapter.save_user already knows to pick up
    first_name/last_name from cleaned_data, so no extra wiring needed."""

    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name", required=False)

    field_order = ["first_name", "last_name", "email", "password1", "password2"]
