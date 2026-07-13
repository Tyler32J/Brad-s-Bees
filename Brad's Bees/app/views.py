from django.shortcuts import render, redirect
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib import messages
from .forms import *
from .models import *

# Create your views here.
def _send_submission_email(submission, files):
    subject = "New Brad's Bees Order"
    message = f"""
    You have received a new Order.

    Name: {submission.name}
    Email: {submission.email}
    Phone: {submission.phone}
    Service: {submission.service}

    Message:
        {submission.message}
            """

    if files:
        message += "\nAttached images:\n"
        for f in files:
            message += f"- {f.name}\n"

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.ORDER_NOTIFICATION_EMAIL],
    )

    for f in files:
        email.attach(f.name, f.read(), f.content_type)

    email.send(fail_silently=False)
    
def render_home_page(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save()

            SubmissionImage.objects.bulk_create([
                SubmissionImage(submission=submission, image=f)
                for f in request.FILES.getlist('images')
            ])

            messages.success(request, "Form submitted successfully!")
            return redirect('home')

    else:
        form = SubmissionForm()

    return render(request, "home.html", {"form": form})

def bee_removal(request):
    return render(request, "bee_removal.html")

def render_services_page(request):
    return render(request, "services.html")

def render_educational_page(request):
    return render(request, "educational.html")

def render_gallery(request):
    return render(request, "gallery.html")

def render_index(request):
    return render(request, "index.html")

