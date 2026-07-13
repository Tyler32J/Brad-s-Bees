from django.shortcuts import render, redirect
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib import messages
from .forms import *
from .models import *

# Create your views here.

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

def contact_view(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            submission = form.save()

            files = request.FILES.getlist('images')
            for f in files:
                SubmissionImage.objects.create(
                    submission=submission,
                    image = f
                )

            subject = "New Contact Form Submission"
            message = f"""

            You have received a new contact form submission.

            Name: {submission.name}
            Email: {submission.email}
            Phone: {submission.phone}
            Service Requested: {submission.service}

            Message:
            {submission.message}

            """

            # message += "\nAttached images:\n"
            # for f in request.FILES.getlist('images'):
            #     print(request.FILES)
            #     print(request.FILES.getlist("images"))
            #     for f in request.FILES.getlist("images"):
            #         print(
            #             f"Name: {f.name}, "
            #             f"Size: {f.size}, "
            #             f"Content Type: {f.content_type}"
            #         )
            #     message += f"- {f.name}\n"
            # print("\nFILES RECEIVED:")
            # print(request.FILES)

            # files = request.FILES.getlist("images")
            # print(f"Number of files: {len(files)}")

            # for f in files:
            #     print(
            #         f"Filename: {f.name} | "
            #         f"Size: {f.size} | "
            #         f"Type: {f.content_type}"
            #     )
            files = request.FILES.getlist("images")

            print("\n===== FILE DEBUG =====")
            print(request.FILES)
            print(f"Number of files: {len(files)}")

            message += "\nAttached images:\n"

            for f in files:
                print(
                    f"Filename: {f.name}\n"
                    f"Size: {f.size}\n"
                    f"Content Type: {f.content_type}\n"
                )

                message += f"- {f.name}\n"

            default_from = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
            recipient = (getattr(settings, "ORDER_NOTIFICATION_EMAIL", "") or "").strip()

            if not default_from or not recipient:
                messages.warning(
                    request,
                    "Your submission was saved, but email is not configured yet.",
                )
                return redirect('contact')

            email = EmailMessage(
                 subject=subject,
                 body=message,
                 from_email=default_from,
                 to=[recipient],
            )

            print("\n===== ATTACHING FILES =====")

            for f in files:
                f.seek(0)
                data = f.read()

                print(f"Attaching {f.name} ({len(data)} bytes)")

                email.attach(
                    filename=f.name,
                    content=data,
                    mimetype=f.content_type,
                )

            # try:
            #     email.send()
            # except Exception as e:
            #     print(f"Email send failed: {e}")
            # # email.send()

            try:
                result = email.send()

                print(f"Email send result: {result}")
                _send_auto_reply(submission, files)
                messages.success(request, "Form submitted successfully!")
            except Exception as e:
                print(f"Email send failed: {e}")
                messages.error(
                    request,
                    "Your information was saved, but we couldn't send the notification email."
                )

            sub_count = Submission.objects.count()
            print(f"\nSUB COUNT: {sub_count}") # bash test for sub C func.

            image_count = SubmissionImage.objects.count()
            print(f"IMG COUNT: {image_count}\n") # bash test for img C func.

            return redirect('contact')
    
            
    else:
        form = SubmissionForm()

    return render(request, 'contact.html', {'form': form})



### FOR BRAD ###

# Step-by-step:
# Go to your Google account:
# https://myaccount.google.com/security

# Turn ON:
# 2-Step Verification (required)

# After that, go to:
# https://myaccount.google.com/apppasswords

# Create a new app password:
# App: Mail
# Device: Other → type "Django"

# Google will give you a 16-character password like:
# abcd efgh ijkl mnop



### FOR ME ###

# in settings.py:
# EMAIL_HOST_PASSWORD = 'abcdefghijklmnop'  # ← app password (NO spaces)