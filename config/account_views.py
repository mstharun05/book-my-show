from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import redirect, render
from django import forms
from django.contrib.auth.decorators import login_required


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email')


class EmailForm(forms.Form):
    email = forms.EmailField()


@login_required
def account_email(request):
    form = EmailForm(request.POST if request.method == 'POST' else None, initial={'email': request.user.email})
    if request.method == 'POST' and form.is_valid():
        request.user.email = form.cleaned_data['email']
        request.user.save(update_fields=['email'])
        return redirect('payments:history')
    return render(request, 'registration/email.html', {'form': form})


def signup(request):
    form = SignupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("discovery:movie_list")
    return render(request, "registration/signup.html", {"form": form})
