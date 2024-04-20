from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.http import HttpResponseRedirect, HttpResponse, HttpResponseNotFound
from stripe import Coupon
from accounts.models import Cart, CartItems
from .models import Profile
from products.models import *
import razorpay
from django.conf import settings

def login_page(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_obj = User.objects.filter(username=email)

        if not user_obj.exists():
            messages.warning(request, 'Account not found.')
            return HttpResponseRedirect(request.path_info)

        if not user_obj[0].profile.is_email_verified:
            messages.warning(request, 'Your account is not verified.')
            return HttpResponseRedirect(request.path_info)

        user_obj = authenticate(username=email, password=password)
        if user_obj:
            login(request, user_obj)
            return redirect('/')

        messages.warning(request, 'Invalid credentials')
        return HttpResponseRedirect(request.path_info)

    return render(request, 'accounts/login.html')


def register_page(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_obj = User.objects.filter(username=email)

        if user_obj.exists():
            messages.warning(request, 'Email is already taken.')
            return HttpResponseRedirect(request.path_info)

        user_obj = User.objects.create(first_name=first_name, last_name=last_name, email=email, username=email)
        user_obj.set_password(password)
        user_obj.save()

        messages.success(request, 'An email has been sent to your mail.')
        return HttpResponseRedirect(request.path_info)

    return render(request, 'accounts/register.html')


def activate_email(request, email_token):
    try:
        user = Profile.objects.get(email_token=email_token)
        user.is_email_verified = True
        user.save()
        return redirect('/')
    except Profile.DoesNotExist:
        return HttpResponse('Invalid Email token')


def add_to_cart(request, uid):
    variant = request.GET.get('variant')
    product = Product.objects.get(uid=uid)
    user = request.user
    cart, _ = Cart.objects.get_or_create(user=user, is_paid=False)
    
    cart_items = CartItems.objects.create(cart=cart, product=product)
    
    if variant:
        size_variant = SizeVariant.objects.get(size_name=variant)
        cart_items.size_variant = size_variant
        cart_items.save()
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def remove_cart(request, cart_item_uid):
    try:
        cart_item = CartItems.objects.get(uid=cart_item_uid)
        cart_item.delete()
    except CartItems.DoesNotExist:
        pass
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def cart(request):
    cart_obj = None
    try:
        cart_obj = Cart.objects.get(is_paid=False, user=request.user)
    except Exception as e:
        print(e)
        
        
    if request.method == 'POST':
        coupon = request.POST.get('coupon')
        coupon_obj = Coupon.objects.filter(coupon_code__icontains=coupon).first()
        
        if not coupon_obj:
            messages.warning(request, "Invalid Coupon.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        if cart_obj.coupon:
            messages.warning(request, "Coupon Already Exists.")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        if cart_obj.get_cart_total() < coupon_obj.minimum_amount:
            messages.warning(request, f'Amount should be greater than {coupon_obj.minimum_amount}')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        if coupon_obj.is_expired:
            messages.warning(request, 'Coupon Expired')
            return HttpResponseRedirect(request.META.get('HTTP_REFERER'))
        
        cart_obj.coupon = coupon_obj
        cart_obj.save()
        messages.success(request, "Coupon Applied.")
        return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

    if cart_obj:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY, settings.RAZORPAY_SECRET))
        total_amount_in_paise = cart_obj.get_cart_total() * 100
        try:
            payment = client.order.create({'amount': total_amount_in_paise, 'currency': 'INR', 'payment_capture': 1})
            cart_obj.razor_pay_order_id = payment['id']
            cart_obj.save()
        except Exception as e:
            print("Razorpay Error:", e)
            payment = None
        
    else:
        payment = None

    context = {'cart': cart_obj, 'payment': payment}  
    return render(request, 'accounts/cart.html', context)


def remove_coupon(request, cart_id):
    try:
        cart = Cart.objects.get(uid=cart_id)
        cart.coupon = None
        cart.save()
        messages.success(request, "Coupon Removed.")
    except Cart.DoesNotExist:
        messages.error(request, "Cart not found.")
    
    return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def success(request):
    order_id = request.GET.get('order_id')
    try:
        cart = Cart.objects.get(razor_pay_order_id=order_id)
        cart.is_paid = True
        cart.save()
        return HttpResponse('Payment Successful')
    except Cart.DoesNotExist:
        return HttpResponseNotFound('Order ID not found')
    except Exception as e:
        return HttpResponse('An error occurred: ' + str(e))
