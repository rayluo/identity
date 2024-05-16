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


#. Add configuration to your ``app.py`` for `Quart-session <https://github.com/kroketio/quart-session>`, a package which is automatically installed when you install ``identity[quart]``::

    app.config['SESSION_TYPE'] = 'redis'
    # Point this to your Redis instance
    app.config['SESSION_URI'] = 'redis://localhost:6379'
    

Sign In and Sign Out
----------------------------------

#. In your web project's ``app.py``, decorate some views with the
   :py:func:`identity.flask.Auth.login_required` decorator.
   It will automatically trigger sign-in. ::

    @app.route("/")
    @auth.login_required
    async def index(*, context):
        user = context['user']
        ...

#. In your web project's any template that you see fit,
   add this URL to present the logout link::

    <a href="{{ url_for('identity.logout') }}">Logout</a>


API reference
--------------------------

.. autoclass:: identity.quart.Auth
   :members:
   :inherited-members:

   .. automethod:: __init__

