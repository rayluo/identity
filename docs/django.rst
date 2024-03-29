Identity for Django
===================

Prerequisite
------------

Create a hello world web project in Django.

You can use
`Django's own tutorial, part 1 <https://docs.djangoproject.com/en/5.0/intro/tutorial01/>`_
as a reference. What we need are basically these steps:

1. ``django-admin startproject mysite``
2. ``python manage.py migrate``
3. ``python manage.py runserver localhost:5000``
   You must use a port matching your redirect_uri that you registered.

4. Now, add an `index` view to your project.
   For now, it can simply return a "hello world" page to any visitor::

    from django.http import HttpResponse
    def index(request):
        return HttpResponse("Hello, world. Everyone can read this line.")

Django configuration
--------------------

1. Firstly, create an instance of the :py:class:`identity.django.Auth` object,
   and assign it to a global variable inside your ``settings.py``::

    import os
    from dotenv import load_dotenv
    from identity.django import Auth
    load_dotenv()
    AUTH = Auth(
        os.getenv('CLIENT_ID'),
        client_credential=os.getenv('CLIENT_SECRET'),
        redirect_uri=os.getenv('REDIRECT_URI'),
        ...,  # See below on how to feed in the authority url parameter
        )

   .. include:: auth.rst

2. Inside the same ``settings.py`` file,
   add ``"identity"`` into the ``INSTALLED_APPS`` list,
   to enable the default templates came with the identity package::

    INSTALLED_APPS = [
        ...,
        "identity",
    ]

3. Add the built-in views into your ``urls.py``::

    from django.conf import settings

    urlpatterns = [
        settings.AUTH.urlpattern,
        ...
        ]

Django Web App Sign In
----------------------

4. In your web project's ``views.py``, decorate some views with the
   :py:func:`identity.django.Auth.login_required` decorator::

    from django.conf import settings

    @settings.AUTH.login_required
    def index(request, *, context):
        user = context['user']
        return HttpResponse(f"Hello, {user.get('name')}.")

Web app that logs in users and calls a web API on their behalf
--------------------------------------------------------------

5. Decorate your token-consuming views using the same
   :py:func:`identity.django.Auth.login_required` decorator,
   this time  with a parameter ``scopes=["your_scope_1", "your_scope_2"]``.

   Then, inside your view, the token will be readily available via
   ``context['access_token']``. For example::

    @settings.AUTH.login_required(scopes=["your_scope"])
    def call_api(request, *, context):
        api_result = requests.get(  # Use access token to call a web api
            "https://your_api.example.com",
            headers={'Authorization': 'Bearer ' + context['access_token']},
            timeout=30,
        ).json()  # Here we assume the response format is json
        ...

All of the content above are demonstrated in
`this django web app sample <https://github.com/Azure-Samples/ms-identity-python-webapp-django>`_.


API for Django web projects
---------------------------

.. autoclass:: identity.django.Auth
   :members:
   :inherited-members:

   .. automethod:: __init__

