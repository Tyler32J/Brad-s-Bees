from django.shortcuts import render, redirect
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib import messages
import traceback
from .forms import *
from .models import *

# Create your views here.
def _send_submission_email(submission, files):
    default_from = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    recipient = (getattr(settings, "ORDER_NOTIFICATION_EMAIL", "") or "").strip()

    if not default_from or not recipient:
        return

    subject = "New Brad's Bees Submission"
    message = f"""
    You have received a new submission.

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
        from_email=default_from,
        to=[recipient],
    )

    for f in files:
        f.seek(0)
        email.attach(f.name, f.read(), f.content_type)

    email.send(fail_silently=False)


def _send_auto_reply(submission, files):
    default_from = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()

    if not default_from or not submission.email:
        return

    reply_subject = f"Brad's Bees Submission #{submission.id} - Confirmation"
    reply_body = f"""
New Brad's Bees submission received.

Customer:
{submission.name}
Email: {submission.email}
Phone: {submission.phone}

Service Requested:
{submission.service}

Message:
{submission.message}

Thank you for reaching out. We will review your submission and get back to you soon.
If you need immediate assistance, you can call us at 985-612-0241.
"""

    reply_email = EmailMessage(
        subject=reply_subject,
        body=reply_body.strip(),
        from_email=default_from,
        to=[submission.email],
    )

    for f in files:
        f.seek(0)
        reply_email.attach(f.name, f.read(), f.content_type)

    reply_email.send(fail_silently=False)
    
def render_home_page(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save()

            SubmissionImage.objects.bulk_create([
                SubmissionImage(submission=submission, image=f)
                for f in request.FILES.getlist('images')
            ])

            try:
                files = request.FILES.getlist('images')
                _send_submission_email(submission, files)
                _send_auto_reply(submission, files)
            except Exception as exc:
                print(f"Email send failed: {exc}")
                traceback.print_exc()

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

