# Identity library

<!-- The following summary is reused in, and needs to be in-sync with, the docs/index.rst -->
This Identity library is an authentication/authorization library that:

* Suitable for apps that are targeting end users on
  [Microsoft identity platform, a.k.a. Microsoft Entra ID](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-overview)
  (which includes Work or school accounts provisioned through Azure AD,
  and Personal Microsoft accounts such as Skype, Xbox, Outlook.com).
* Currently designed for web apps,
  regardless of which Python web framework you are using.
* Provides a set of high level API that is built on top of, and easier to be used than
  [Microsoft's MSAL Python library](https://github.com/AzureAD/microsoft-authentication-library-for-python).
* Written in Python, for Python apps.

> DISCLAIMER: The code in this repo is not officially supported by Microsoft and is not intended for production use.
> The intention of this repo is to unblock customers who would like to use a higher level API,
> before such an API has been migrated to an Microsoft library with official support. Migration of this API to official support is not guaranteed and is not currently on the MSAL roadmap.
> Please ensure to fully test any code used from this repository to ensure it works in your environment.

## Scenarios supported

<table border=1>
  <tr>
    <th></th>
    <th>Microsoft Entra ID</th>
    <th>Microsoft Entra External ID</th>
    <th>Microsoft Entra External ID with Custom Domain</th>
    <th>Azure AD B2C</th>
  </tr>

  <tr>
    <th>App Registration</th>
    <td><!-- See https://github.com/github/cmark-gfm/issues/12 -->

Following only the step 1, 2 and 3  of this
[Quickstart: Add sign-in with Microsoft to a Python web app](https://learn.microsoft.com/entra/identity-platform/quickstart-web-app-python-sign-in?tabs=windows)

</td>
    <td>

Follow only the page 1 of this [Tutorial: Prepare your customer tenant ...](https://learn.microsoft.com/entra/external-id/customers/tutorial-web-app-python-flask-prepare-tenant)

</td>
    <td>

Coming soon.

</td>
    <td>

Following only the step 1 and 2 (including 2.1 and 2.2) of this
[Configure authentication in a sample Python web app by using Azure AD B2C](https://learn.microsoft.com/azure/active-directory-b2c/configure-authentication-sample-python-web-app?tabs=linux)

</td>
  </tr>

  <tr>
    <th>Web App Sign In & Sign Out</th>
    <td colspan=4>

By using this library, it will automatically renew signed-in session when the ID token expires.

* [Sample written in ![Django](https://raw.githubusercontent.com/rayluo/identity/dev/docs/django.webp)](https://github.com/Azure-Samples/ms-identity-python-webapp-django)
* [Sample written in ![Flask](https://raw.githubusercontent.com/rayluo/identity/dev/docs/flask.webp)](https://github.com/Azure-Samples/ms-identity-python-webapp)
* [Sample written in ![Quart](https://raw.githubusercontent.com/rayluo/identity/dev/docs/quart.webp)](https://github.com/rayluo/python-webapp-quart)
* Need support for more web frameworks?
  [Upvote existing feature request or create a new one](https://github.com/rayluo/identity/issues?q=is%3Aissue+is%3Aopen+sort%3Areactions-%2B1-desc)

</td>
  </tr>

  <tr>
    <th>How to customize the login page</th>
    <td colspan=4>

The default login page will typically redirect users to your Identity Provider,
so you don't have to customize it.
But if the default login page is shown in your browser,
you can read its HTML source code, and find the how-to instructions there.

</td>
  </tr>

  <tr>
    <th>Web App Calls a web API</th>
    <td colspan=4>

This library supports:

+ Incremental consent. If the user needs to consent to more permissions,
  the library will automatically redirect the user to the consent page.
+ Automatically cache the access token and renew it when needed

They are demonstrated by the same samples above.

</td>
  </tr>

  <tr>
    <th>Web API Calls another web API (On-behalf-of)</th>
    <td colspan=4>

In roadmap.

</td>
  </tr>

  <tr>
    <th>How to build the samples above from scratch</th>
    <td colspan=4>

Read our [docs here](https://identity-library.readthedocs.io/en/latest/)

</td>
  </tr>

  <tr>
    <th>Other scenarios</th>
    <td colspan=4>

[Upvote existing feature request or create a new one](https://github.com/rayluo/identity/issues?q=is%3Aissue+is%3Aopen+sort%3Areactions-%2B1-desc)

</td>
  </tr>

</table>


## Installation

This package is [available on PyPI](https://pypi.org/project/identity/).
Choose the package declaration that matches your web framework:

* Django: `pip install identity[django]`
* Flask: `pip install identity[flask]`
* Quart: `pip install identity[quart]`

## Versions

This library follows [Semantic Versioning](http://semver.org/).
Your project should declare `identity` dependency with proper lower and upper bound.

You can find the changes for each version under
[Releases](https://github.com/rayluo/identity/releases).

