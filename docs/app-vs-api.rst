.. note::

    Web Application (a.k.a. website) and Web API are different scenarios,
    both supported by the same Identity Auth component with different decorators.
    Make sure you are using the right decorator for your scenario.

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Aspects
     - Web Application (a.k.a. website)
     - Web API
   * - **Definition**
     - A complete solution that users interact with directly through their browsers.
     - A back-end system that provides data (typically in JSON format) to front-end or other system.
   * - **Functionality**
     - | - Users interact with views (HTML user interfaces) and data.
       | - Users sign in and establish their sessions.
     - | - Does not return views (in HTML); only provides data.
       | - Other systems (clients) hit its endpoints.
       | - Clients presents a token to access your API.
       | - Each request has no session. They are stateless.
   * - **Identity component**
     - Same ``Auth`` class
     - Same ``Auth`` class
   * - **Decorator to use**
     - ``@auth.login_required``
     - ``@auth.authorization_required``

