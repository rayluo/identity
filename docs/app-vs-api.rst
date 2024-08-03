.. note::

    Web Application (a.k.a. website) and Web API are different,
    and are supported by different Identity components.
    Make sure you are using the right component for your scenario.

    +-------------------------+---------------------------------------------------+-------------------------------------------------------+
    | Aspects                 | Web Application (a.k.a. website)                  | Web API                                               |
    +=========================+===================================================+=======================================================+
    | **Definition**          | A complete solution that users interact with      | A back-end system that provides data (typically in    |
    |                         | directly through their browsers.                  | JSON format) to front-end or other system.            |
    +-------------------------+---------------------------------------------------+-------------------------------------------------------+
    | **Functionality**       | - Users interact with views (HTML user interfaces)| - Does not return views (in HTML); only provides data.|
    |                         |   and data.                                       | - Other systems (clients) hit its endpoints.          |
    |                         | - Users sign in and establish their sessions.     | - Clients presents a token to access your API.        |
    |                         |                                                   | - Each request has no session. They are stateless.    |
    +-------------------------+---------------------------------------------------+-------------------------------------------------------+

