.. note::

    Web Application and Web API are different, and are supported by different Identity components.
    Make sure you are using the right component for your scenario.

    +-------------------------+---------------------------------------------------+-------------------------------------------------------+
    | Aspect                  | Web Application                                   | Web API                                               |
    +=========================+===================================================+=======================================================+
    | **Definition**          | A complete solution that users interact with      | A back-end system that provides data to other systems |
    |                         | directly through their browsers.                  | without views.                                        |
    +-------------------------+---------------------------------------------------+-------------------------------------------------------+
    | **Functionality**       | - Users interact with views (HTML user interfaces)| - Does not return views (in HTML); only provides data.|
    |                         |   and data.                                       | - Other systems (clients) hit its endpoints.          |
    +-------------------------+---------------------------------------------------+-------------------------------------------------------+

