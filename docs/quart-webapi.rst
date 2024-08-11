Identity for a Quart Web API
==============================

.. include:: app-vs-api.rst

Prerequisite
------------

Create `a hello world web project in Quart <https://quart.palletsprojects.com/en/latest/quick_start.html>`_.
Here we assume the project's main file is named ``app.py``.


Configuration
-------------

#. Install dependency by ``pip install identity[quart]``

#. Create an instance of the :py:class:`identity.quart.Auth` object,
   and assign it to a global variable inside your ``app.py``::

    import os
    from quart import Quart
    from identity.quart import Auth

    app = Quart(__name__)
    auth = Auth(
        client_id=os.getenv('CLIENT_ID'),
        ...=...,  # See below on how to feed in the authority url parameter
        )

   .. include:: auth.rst


Quart Web API protected by an access token
------------------------------------------

#. In your web project's ``app.py``, decorate some views with the
   :py:func:`identity.quart.Auth.authorization_required` decorator.
   It will automatically put validated token claims into the ``context`` dictionary,
   under the key ``claims``.
   or emit an HTTP 401 or 403 response if the token is missing or invalid.

   ::

    @app.route("/")
    @auth.authorization_required(expected_scopes={
        "your_scope_1": "api://your_client_id/your_scope_1",
        "your_scope_2": "api://your_client_id/your_scope_2",
    })
    async def index(*, context):
        claims = context['claims']
        # The user is uniquely identified by claims['sub'] or claims["oid"],
        # claims['tid'] and/or claims['iss'].
        return {"message": f"Data for {claims['sub']}@{claims['tid']}"}

All of the content above follows the same pattern as
`Flask web API sample <https://github.com/Azure-Samples/ms-identity-python-webapi-flask>`_
but uses async/await syntax for Quart.

API for Quart web API projects
------------------------------

.. autoclass:: identity.quart.Auth
   :members:
   :inherited-members:

   .. automethod:: __init__
