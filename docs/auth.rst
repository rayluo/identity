.. tip::

    We recommend
    `storing settings in environment variables <https://12factor.net/config>`_.
    The snippet above read data from environment variables.

..
   This is a comment.
   The table below was built via https://tableconvert.com/restructuredtext-generator

.. admonition:: Initializing Auth object differently based on Identity Provider type

    +------------------------------------------------+-----------------------------------------------------------+--------------------------------------------------------------------------+
    |                                                | Its authority URL looks like                              | Initialize Auth() object like this                                       |
    +================================================+===========================================================+==========================================================================+
    | Microsoft Entra ID                             | ``https://login.microsoftonline.com/tenant``              | Auth(..., authority=url, ...)                                            |
    +------------------------------------------------+-----------------------------------------------------------+                                                                          +
    | Microsoft Entra External ID                    | ``https://contoso.ciamlogin.com/contoso.onmicrosoft.com`` |                                                                          |
    +------------------------------------------------+-----------------------------------------------------------+--------------------------------------------------------------------------+
    | Microsoft Entra External ID with Custom Domain | ``https://contoso.com/tenant``                            | Auth(..., oidc_authority=url, ...)                                       |
    +------------------------------------------------+-----------------------------------------------------------+--------------------------------------------------------------------------+
    | Azure AD B2C                                   | N/A                                                       | Auth(..., b2c_tenant_name="contoso", b2c_signup_signin_user_flow="susi") |
    +------------------------------------------------+-----------------------------------------------------------+--------------------------------------------------------------------------+

