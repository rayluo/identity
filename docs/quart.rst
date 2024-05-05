Identity for Quart
==================

Prerequisite
------------

Create `a hello world web project in Quart <https://quart.palletsprojects.com/en/latest/tutorials/quickstart.html>`_.
Here we assume the project's main file is named ``app.py``.


Configuration
--------------------------------

#. Install dependency by ``pip install identity[quart]``

#. Create an instance of the :py:class:`identity.quart.Auth` object,
   and assign it to a global variable inside your ``app.py``::

    import os

    from quart import Quart
    from identity.quart import Auth

    app = Quart(__name__)

    auth = Auth(
        app,
        os.getenv('CLIENT_ID'),
        client_credential=os.getenv('CLIENT_SECRET'),
        redirect_uri=os.getenv('REDIRECT_URI'),
        ...,  # See below on how to feed in the authority url parameter
        )

   .. include:: auth.rst


#. Setup session management with the `Quart-session <https://github.com/kroketio/quart-session>`_ package, which currently supports either Redis or MongoDB backing stores. To use Redis as the session store, you should first install the package with the extra dependency::

    pip install quart-session[redis]

#. Then add configuration to ``app.py`` pointing to your Redis instance::

    app.config['SESSION_TYPE'] = 'redis'
    app.config['SESSION_URI'] = 'redis://localhost:6379'


Sign In and Sign Out
----------------------------------

#. In your web project's ``app.py``, decorate some views with the
   :py:func:`identity.quart.Auth.login_required` decorator.
   It will automatically trigger sign-in. ::

    @app.route("/")
    @auth.login_required
    async def index(*, context):
        user = context['user']
        ...

#. In your web project's any template that you see fit,
   add this URL to present the logout link::

    <a href="{{ url_for('identity.logout') }}">Logout</a>


Web app that logs in users and calls a web API on their behalf
--------------------------------------------------------------

#. Decorate your token-consuming views using the same
   :py:func:`identity.quart.Auth.login_required` decorator,
   this time with a parameter ``scopes=["your_scope_1", "your_scope_2"]``.

   Then, inside your view, the token will be readily available via
   ``context['access_token']``. For example::

    @app.route("/call_api")
    @auth.login_required(scopes=["your_scope_1", "your_scope_2"])
    async def call_api(*, context):
        async with httpx.AsyncClient() as client:
            api_result = await client.get(  # Use access token to call a web api
                os.getenv("ENDPOINT"),
                headers={'Authorization': 'Bearer ' + context['access_token']},
            )
        return await render_template('display.html', result=api_result)


All of the content above are demonstrated in
`this Quart web app sample <https://github.com/rayluo/python-webapp-quart>`_.


API reference
--------------------------

.. autoclass:: identity.quart.Auth
   :members:
   :inherited-members:

   .. automethod:: __init__

