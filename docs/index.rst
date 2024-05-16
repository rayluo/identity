======================
Identity Documentation
======================

Summary
=======

.. The following summary is reused in, and needs to be in-sync with, the ../README.md

This Identity library is a Python authentication/authorization library that:

* Suitable for apps that are targeting end users on
  `Microsoft identity platform <https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-overview>`_, which includes:

  - Microsoft Entra ID
    (including Work or school accounts provisioned through Azure AD,
    Personal Microsoft accounts such as Skype, Xbox, Outlook.com)
  - Microsoft Entra External ID
  - Microsoft Entra External ID with Custom Domain
  - Azure AD B2C

* Built on top of
  `Microsoft's MSAL Python library <https://github.com/AzureAD/microsoft-authentication-library-for-python>`_
  and tailored for web apps.

  - a high level API for
    `Django web framework <https://www.djangoproject.com/>`_,
  - a high level API for
    `Flask web framework <https://flask.palletsprojects.com/en/3.0.x/>`_,
  - and a low level API which would likely work for any Python web framework.

* Supports these features/scenarios:

  - Sign-in/sign-out

    + Automatically renew signed-in session when the ID token expires

  - Acquires an access token to call a web API

    + Incremental consent. If the user needs to consent to more permissions,
      the library will automatically redirect the user to the consent page.
    + Automatically cache the access token and renew it when needed

.. toctree::
   :maxdepth: 2
   :caption: Contents:
   :hidden:

   django
   flask
   quart
   abc
   generic

.. note::

    Only APIs and their parameters documented in this document are part of public API,
    with guaranteed backward compatibility for the entire 1.x series.

    Other modules in the source code are all considered as internal helpers,
    which could change at anytime in the future, without prior notice.

