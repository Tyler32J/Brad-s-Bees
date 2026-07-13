from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from decimal import Decimal
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from .forms import CheckoutForm
from .models import Product, Order, OrderItem, Cart, Item


def _get_or_create_cart(request):
    """Return cart for current user (if authenticated) or current guest session."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(
            user=request.user,
            defaults={"session_key": request.session.session_key},
        )
        return cart

    if not request.session.session_key:
        request.session.create()

    cart, _ = Cart.objects.get_or_create(
        user=None,
        session_key=request.session.session_key,
    )
    return cart


def _migrate_legacy_session_cart(request, cart):
    """Move old session-based cart payload into DB cart and clear legacy key."""
    legacy_cart = request.session.get("cart", {})
    if not legacy_cart:
        return

    for product_id, payload in legacy_cart.items():
        try:
            product = Product.objects.get(id=int(product_id))
        except (Product.DoesNotExist, ValueError, TypeError):
            continue

        quantity = 1
        if isinstance(payload, dict):
            quantity = int(payload.get("quantity", 1))
        elif isinstance(payload, int):
            quantity = payload

        if quantity <= 0:
            continue

        item, created = Item.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={"quantity": quantity},
        )
        if not created:
            item.quantity += quantity
            item.save(update_fields=["quantity"])

    request.session["cart"] = {}
    request.session.modified = True


def _build_cart_context(cart):
    """Build cart rows and totals for templates and checkout."""
    cart_items = []
    subtotal = Decimal("0")
    item_rows = cart.items.select_related("product").all()

    for row in item_rows:
        product = row.product
        unit_price = product.price or Decimal("0")
        item_total = unit_price * row.quantity
        subtotal += item_total
        cart_items.append({
            "id": product.id,
            "name": product.name,
            "variant": product.variant or "",
            "price": float(unit_price),
            "quantity": row.quantity,
            "image": product.image,
            "total": float(item_total),
            "product": product,
            "unit_price": unit_price,
            "line_total": item_total,
        })

    shipping = Decimal("0") if subtotal > 50 else Decimal("5")
    total = subtotal + shipping
    cart_count = sum(item["quantity"] for item in cart_items)

    return {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total,
        "cart_count": cart_count,
    }


def _send_order_notification(order, cart_items):
    """Email order details to business inbox and customer email when available."""
    default_from = (getattr(settings, "DEFAULT_FROM_EMAIL", "") or "").strip()
    primary_recipient = (getattr(settings, "ORDER_NOTIFICATION_EMAIL", "") or "").strip()

    if not default_from or not primary_recipient:
        return "not_configured"

    recipients = []

    if primary_recipient:
        recipients.append(primary_recipient)
    if order.email:
        recipients.append(order.email)

    recipients = list(dict.fromkeys(recipients))
    if not recipients:
        return "skipped"

    item_lines = []
    for item in cart_items:
        product = item["product"]
        variant = f" ({product.variant})" if product.variant else ""
        item_lines.append(
            f"- {product.name}{variant} x {item['quantity']} @ ${item['unit_price']:.2f} = ${item['line_total']:.2f}"
        )

    message = "\n".join([
        f"New order received: #{order.id}",
        "",
        "Customer:",
        f"{order.first_name} {order.last_name}",
        f"Email: {order.email}",
        f"Phone: {order.phone}",
        "",
        "Shipping Address:",
        f"{order.address_line_1}",
        f"{order.address_line_2}" if order.address_line_2 else "",
        f"{order.city}, {order.state} {order.zip_code}",
        "",
        "Items:",
        *item_lines,
        "",
        f"Subtotal: ${order.subtotal:.2f}",
        f"Shipping: ${order.shipping:.2f}",
        f"Total: ${order.total:.2f}",
        "",
        f"Notes: {order.notes or 'None'}",
    ])

    try:
        send_mail(
            subject=f"New Brad's Bees Order #{order.id}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        return "sent"
    except Exception:
        return "failed"

def store_view(request):
    """Display all products in the shop"""
    cart = _get_or_create_cart(request)
    _migrate_legacy_session_cart(request, cart)
    cart_context = _build_cart_context(cart)

    products = Product.objects.all()
    context = {
        'products': products,
        'cart_count': cart_context['cart_count']
    }
    return render(request, 'shop.html', context)

def add_to_cart(request, product_id):
    """Add a product to the shopping cart (DB-backed)."""
    product = get_object_or_404(Product, id=product_id)
    cart = _get_or_create_cart(request)
    _migrate_legacy_session_cart(request, cart)

    cart_item, created = Item.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1},
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save(update_fields=['quantity'])

    cart_context = _build_cart_context(cart)
    
    # Return JSON if AJAX request, otherwise redirect
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'cart_count': cart_context['cart_count']
        })
    
    return redirect('cart')

def cart_view(request):
    """Display the shopping cart"""
    cart = _get_or_create_cart(request)
    _migrate_legacy_session_cart(request, cart)
    cart_context = _build_cart_context(cart)
    
    context = {
        'cart_items': cart_context['cart_items'],
        'subtotal': f"{cart_context['subtotal']:.2f}",
        'shipping': f"{cart_context['shipping']:.2f}",
        'total': f"{cart_context['total']:.2f}",
        'cart_count': cart_context['cart_count']
    }
    return render(request, 'cart.html', context)

def remove_from_cart(request, product_id):
    """Remove an item from the shopping cart"""
    cart = _get_or_create_cart(request)
    _migrate_legacy_session_cart(request, cart)
    Item.objects.filter(cart=cart, product_id=product_id).delete()
    
    return redirect('cart')

def update_cart(request, product_id):
    """Update the quantity of an item in the cart"""
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        cart = _get_or_create_cart(request)
        _migrate_legacy_session_cart(request, cart)

        cart_item = Item.objects.filter(cart=cart, product_id=product_id).first()
        if cart_item:
            if quantity > 0:
                cart_item.quantity = quantity
                cart_item.save(update_fields=['quantity'])
            else:
                cart_item.delete()
    
    return redirect('cart')

# --- Checkout View ---
def checkout_view(request):
    """Display the checkout page."""
    cart = _get_or_create_cart(request)
    _migrate_legacy_session_cart(request, cart)
    cart_context = _build_cart_context(cart)

    cart_items = cart_context["cart_items"]
    subtotal = cart_context["subtotal"]
    shipping = Decimal("0.00")
    total = subtotal + shipping

    if request.method == "POST":
        form = CheckoutForm(request.POST)

        if not cart_items:
            messages.error(request, "Your cart is empty.")
            return redirect("shop")

        if form.is_valid():
            with transaction.atomic():
                order = Order.objects.create(
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    address_line_1=form.cleaned_data["address_line_1"],
                    address_line_2=form.cleaned_data["address_line_2"],
                    city=form.cleaned_data["city"],
                    state=form.cleaned_data["state"],
                    zip_code=form.cleaned_data["zip_code"],
                    notes=form.cleaned_data["notes"],
                    subtotal=subtotal,
                    shipping=shipping,
                    total=total,
                )

                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item["product"],
                        quantity=item["quantity"],
                        unit_price=item["unit_price"],
                        line_total=item["line_total"],
                    )

            email_status = _send_order_notification(order, cart_items)

            cart.items.all().delete()
            request.session["cart"] = {}
            request.session.modified = True
            messages.success(
                request,
                "Thank you for your Order! You will receive a message/email in the following 24 hours.",
            )
            if email_status == "not_configured":
                messages.warning(
                    request,
                    "Order saved, but email is not configured yet. Set DEFAULT_FROM_EMAIL and ORDER_NOTIFICATION_EMAIL in your .env file.",
                )
            if email_status == "failed":
                messages.warning(request, "Order saved, but email notification could not be sent.")
            return redirect("shop")
    else:
        form = CheckoutForm()

    return render(request, "checkout.html", {
        "form": form,
        "cart_items": cart_items,
        "subtotal": subtotal,
        "shipping": shipping,
        "total": total,
        "cart_count": cart_context["cart_count"],
    })
