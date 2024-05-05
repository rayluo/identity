Identity for Flask
==================

Prerequisite
------------

Create `a hello world web project in Flask <https://flask.palletsprojects.com/en/3.0.x/quickstart/#a-minimal-application>`_.
Here we assume the project's main file is named ``app.py``.


Configuration
--------------------------------

#. Install dependency by ``pip install identity[flask]``

#. Add an ``app_config.py`` file containing the following::

    # Tells the Flask-session extension to store sessions in the filesystem
    SESSION_TYPE = "filesystem"

    # In production, your setup may use multiple web servers behind a load balancer,
    # and the subsequent requests may not be routed to the same web server.
    # In that case, you may either use a centralized database-backed session store,
    # or configure your load balancer to route subsequent requests to the same web server
    # by using sticky sessions also known as affinity cookie.
    # [1] https://www.imperva.com/learn/availability/sticky-session-persistence-and-cookies/
    # [2] https://azure.github.io/AppService/2016/05/16/Disable-Session-affinity-cookie-(ARR-cookie)-for-Azure-web-apps.html
    # [3] https://learn.microsoft.com/en-us/azure/app-service/configure-common?tabs=portal#configure-general-settings

#. Create an instance of the :py:class:`identity.flask.Auth` object,
   and assign it to a global variable inside your ``app.py``::

    import os
    from flask import Flask
    from identity.flask import Auth
    import app_config

    app = Flask(__name__)
    app.config.from_object(app_config)

    auth = Auth(
        app,
        os.getenv('CLIENT_ID'),
        client_credential=os.getenv('CLIENT_SECRET'),
        redirect_uri=os.getenv('REDIRECT_URI'),
        ...,  # See below on how to feed in the authority url parameter
        )

   .. include:: auth.rst


Sign In and Sign Out
----------------------------------

#. In your web project's ``app.py``, decorate some views with the
   :py:func:`identity.flask.Auth.login_required` decorator.
   It will automatically trigger sign-in. ::

    @app.route("/")
    @auth.login_required
    def index(*, context):
        user = context['user']
        ...

#. In your web project's any template that you see fit,
   add this URL to present the logout link::

    <a href="{{ url_for('identity.logout') }}">Logout</a>


Web app that logs in users and calls a web API on their behalf
--------------------------------------------------------------

#. Decorate your token-consuming views using the same
   :py:func:`identity.flask.Auth.login_required` decorator,
   this time with a parameter ``scopes=["your_scope_1", "your_scope_2"]``.

   Then, inside your view, the token will be readily available via
   ``context['access_token']``. For example::

    @app.route("/call_api")
    @auth.login_required(scopes=["your_scope_1", "your_scope_2"])
    def call_api(*, context):
        api_result = requests.get(  # Use access token to call a web api
            "https://your_api.example.com",
            headers={'Authorization': 'Bearer ' + context['access_token']},
            timeout=30,
        )
        ...

All of the content above are demonstrated in
`this Flask web app sample <https://github.com/Azure-Samples/ms-identity-python-webapp>`_.

API reference
--------------------------

.. autoclass:: identity.flask.Auth
   :members:
   :inherited-members:

   .. automethod:: __init__

