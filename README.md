# Identity library

<!-- The following summary is reused in, and needs to be in-sync with, the docs/index.rst -->
This Identity library is an authentication/authorization library that:

* Suitable for apps that are targeting end users on
  [Microsoft identity platform](https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-overview)
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

* [Web app that logs in users](https://identity-library.readthedocs.io/en/latest/#web-app-that-logs-in-users)
* [Web app that logs in users and calls a web API on their behalf](https://identity-library.readthedocs.io/en/latest/#web-app-that-logs-in-users-and-calls-a-web-api-on-their-behalf)
* [In roadmap] Protected web API that only authenticated users can access
* [In roadmap] Protected web API that calls another (downstream) web API on behalf of the signed-in user

## Installation

This package is [available on PyPI](https://pypi.org/project/identity/).
You can install it by `pip install identity`.

## Versions

This library follows [Semantic Versioning](http://semver.org/).
Your project should declare `identity` dependency with proper lower and upper bound.

As of this writing, this library is still in preview. Please declare your dependency as
`identity>=0.2,<0.3`.

You can find the changes for each version under
[Releases](https://github.com/rayluo/identity/releases).


## Usage

Sample coming soon.

