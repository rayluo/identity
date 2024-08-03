Identity for a Django Web API
=============================

.. include:: app-vs-api.rst

Prerequisite
------------

Create a hello world web project in Django.

You can use
`Django's own tutorial, part 1 <https://docs.djangoproject.com/en/5.0/intro/tutorial01/>`_
as a reference. What we need are basically these steps:

#. ``django-admin startproject mysite``
#. ``python manage.py migrate`` (Optinoal if your project does not use a database)
#. ``python manage.py runserver localhost:5000``

#. Now, add a new `mysite/views.py` file with an `index` view to your project.
   For now, it can simply return a "hello world" page to any visitor::

    from django.http import JsonResponse
    def index(request):
        return JsonResponse({"message": "Hello, world!"})

Configuration
-------------

#. Install dependency by ``pip install identity[django]``

#. Create an instance of the :py:class:`identity.django.Auth` object,
   and assign it to a global variable inside your ``settings.py``::

    import os
    from identity.django import Auth
    AUTH = Auth(
        client_id=os.getenv('CLIENT_ID'),
        ...=...,  # See below on how to feed in the authority url parameter
        )

   .. include:: auth.rst


Django Web API protected by an access token
-------------------------------------------

#. In your web project's ``views.py``, decorate some views with the
   :py:func:`identity.django.ApiAuth.authorization_required` decorator::

    from django.conf import settings

    @settings.AUTH.authorization_required(expected_scopes={
        "your_scope_1": "api://your_client_id/your_scope_1",
        "your_scope_2": "api://your_client_id/your_scope_2",
    })
    def index(request, *, context):
        claims = context['claims']
        # The user is uniquely identified by claims['sub'] or claims["oid"],
        # claims['tid'] and/or claims['iss'].
        return JsonResponse(
            {"message": f"Data for {claims['sub']}@{claims['tid']}"}
        )


All of the content above are demonstrated in
`this django web app sample <https://github.com/Azure-Samples/ms-identity-python-webapi-django>`_.


API for Django web projects
---------------------------

.. autoclass:: identity.django.ApiAuth
   :members:
   :inherited-members:

   .. automethod:: __init__

