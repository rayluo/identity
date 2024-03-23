Low-level API for generic web projects
======================================

This is low-level API for web projects.
It is documented here only for reference. You do not need to use it directly.
Use the high-level API for your Django or Flask web framework instead.

Web app that logs in users
--------------------------

1. Firstly, create an instance of the :py:class:`identity.web.Auth` object,
   and assign it to a (typically global) variable::

    auth = identity.web.Auth(
        session=session,  # A session object is a key-value storage with a
                          # dict-like interface. Many web frameworks provide this.
        authority="https://login.microsoftonline.com/common",
        client_id="your_app_client_id",
        client_credential="your_secret",
        )

2. Now, in your web app's login controller, call the
   ``auth.log_in(scopes=["your_scope"], redirect_uri="https://your_app.example.com/redirect_uri")``
   (see also :py:meth:`.log_in`)
   to obtain the ``auth_uri`` (and possibly a ``user_code``),
   and then render them into your login html page.

3. The second leg of log-in needs to be implemented in another controller,
   which calls ``auth.complete_log_in(incoming_query_parameters)``
   (see also :py:meth:`.complete_log_in`).
   If its returned dict contains an ``error``, then render the error to end user,
   otherwise your end user has successfully logged in,
   and his/her information is available as a dict returned by
   :meth:`identity.web.Auth.get_user`.
   In particular, the returned dict contains a key named ``sub``,
   whose value is the unique identifier which you can use to represent this end user
   in your app's local database.

4. Don't forget to add one more controller for log out. You do it by calling
   ``auth.log_out("https://your_app.example.com")``.
   Please refer to :meth:`.log_out`'s docs for more details about its return value.

All of the content above are demonstrated in this sample (link to be provided).


Web app that logs in users and calls a web API on their behalf
--------------------------------------------------------------

Building on top of the previous scenario, you just need to call
``auth.get_token_for_user(["your_scope"])`` to obtain a token object.
See :py:meth:`identity.web.Auth.get_token_for_user` for more details.
And you can see it in action in this sample (link to be provided).


Generic API, currently used for Flask web apps
----------------------------------------------

.. autoclass:: identity.web.Auth
   :members:
   :inherited-members:

   .. automethod:: __init__

