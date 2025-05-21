# **Governance Structure**

This document describes the formal governance structure of the marimo project.

## **Mission**

The marimo project builds next-generation developer tools for working with
data that are reproducible and scalable, and that create easy-to-share
artifacts. Our main project is the marimo notebook.

marimo is a reactive Python notebook: run a cell or interact with a UI
element, and marimo automatically runs dependent cells (or marks them as
stale), keeping code and outputs consistent. marimo notebooks are stored as
pure Python, executable as scripts, and deployable as apps. marimo
provides a batteries-included programming environment designed specifically
for working with data. marimo aims to be easy to get started with, while
providing expressivity and extensibility for power users.

## **Code of Conduct**

The marimo community strongly values inclusivity and diversity. Everyone should
treat others with the utmost respect. Everyone in the community must adhere to
the Code of Conduct specified in [the marimo GitHub
repository](https://github.com/marimo-team/marimo/blob/main/CODE_OF_CONDUCT.md).
Violations of this code of conduct may be reported confidentially to Project
Maintainers indicated at that link.

## **Entities**

This section outlines the different entities that exist within the marimo project, their basic role, and how membership of each entity is determined.

### **Benevolent Dictator For Life**

Due to his role in the creation of marimo, [Akshay Agrawal](https://akshayagrawal.com/) holds the title of [Benevolent Dictator For Life (BDFL)](https://en.wikipedia.org/wiki/Benevolent_dictator_for_life).

### **Project Maintainers**

Project Maintainers lead the technical development of the marimo project, and
they are the ultimate authority on the direction of the marimo project. The
current Project Maintainers are:

- Akshay Agrawal ([@akshaya](https://github.com/akshayka))
- Myles Scolnick ([@mscolnick](https://github.com/mscolnick))
- Bennet Meyers ([@bmeyers](https://github.com/bmeyers))

A new maintainer may be added by consensus of the current Project Maintainers
and notification to the Steering Committee.

Before becoming a maintainer, it is expected that the community member will
have been an active participant in the development and maintenance of the marimo
repository for a sustained period of time. This includes triaging issues,
proposing and reviewing pull requests, and updating continuous integration
as needed.

### **Emeritus Project Maintainers**

Emeritus Project Maintainers are community members who were Project
Maintainers, but have stepped back to a less active role. A Project Maintainer
may choose to switch to emeritus status by informing the other Project
Maintainers and the Steering Committee.

### **Steering Committee**

The Steering Committee supports the Project Maintainers by representing marimo
in all administrative and legal capacities. In addition, the Steering
Committee:

- Approves expenditures related to marimo.
- Negotiates and approves contracts with external contractors who provide paid work to marimo.

The current members of the Steering Committee are:

- Akshay Agrawal ([@akshaya](https://github.com/akshayka))
- Myles Scolnick ([@mscolnick](https://github.com/mscolnick))
- Bennet Meyers ([@bmeyers](https://github.com/bmeyers))

A member of the Steering Committee may leave the committee by notifying the
Steering Committee and Project Maintainers. The remaining Steering Committee
members, in consultation with the Project Maintainers, will invite a member of
the community to join in order to maintain a quorum of five members.

## **Decision Making Process**

This section outlines how financial and non-financial decisions are made in the
marimo project.

### **Financial Decisions**

All financial decisions are made by the Steering Committee to ensure any funds
are spent in a manner that furthers the mission of marimo. Financial decisions
require majority approval by Steering Committee members.

Community members proposing decisions with a financial aspect should contact
the Steering Committee directly.

### **Non-financial Decisions**

All non-financial decisions are made via consensus of the Project Maintainers.
Emeritus Project Maintainers are not considered to be Project Maintainers for
this purpose.

Code-related decisions, such as when a pull request is ready to be accepted and
merged, should be discussed via the relevant GitHub issues and pull requests.
If consensus cannot be achieved, the community member proposing the change may
be invited by a project maintainer to present their proposal at a developer
call for further discussion and community input.

Changes to any public API require explicit approval (in the form of an
"Approval" on a GitHub review) from a majority of the Project Maintainers.

Non-code-related decisions, such as long-term strategic planning for marimo,
should either be discussed in a GitHub issue, or tabled as an agenda item and
discussed on a developer call.

If consensus on a non-financial decision cannot be achieved, the final decision
will be made by the BDFL.

The Steering Committee can gain additional decision-making power if the Project
Maintainers decide to delegate.

### **Conflict of Interest**

It is expected that community members will be employed at a wide range of
companies, universities and non-profit organizations. Because of this, it is
possible that members will have conflicts of interest. Such conflicts of
interest include, but are not limited to:

- Financial interests, such as investments, employment or contracting work, outside of marimo that may influence their work on marimo.
- Access to proprietary information of their employer that could potentially leak into their work with marimo.

All members of the Steering Committee shall disclose to the Steering Committee
any conflict of interest they may have. Members with a conflict of interest in
a particular issue may participate in Steering Committee discussions on that
issue, but must recuse themselves from voting.

Project Maintainers and repository maintainers should also disclose conflicts
of interest with other Project Maintainers and step back from decisions when
conflicts of interests are in play.

## **GitHub Permissions**

GitHub permissions are used to control access to the marimo GitHub repository.

Anyone with commit access to the repository is trusted to use it in a way that
is consistent with the Decision Making Process. Those with permissions should
prefer pull requests over direct pushes, ask for feedback on changes if they
are not sure there is a consensus, and follow marimo’s [style
guide](https://github.com/marimo-team/marimo/blob/main/CONTRIBUTING.md) and
development processes.

### **Project Maintainers**

Project Maintainers are added as
[Owners](https://docs.github.com/en/free-pro-team@latest/github/setting-up-and-managing-organizations-and-teams/permission-levels-for-an-organization#permission-levels-for-an-organization)
of the marimo GitHub organization.

### **Emeritus Project Maintainers**

Emeritus Project Maintainers retain the same commit rights as Project
Maintainers, unless they choose to surrender them.

## **Community Involvement**

The marimo project highly values the contributions made by members of the
community. As an open-source project, marimo is both made for the community,
and by the community.

There are three channels that marimo uses to engage with the community.

### **Discord Server**

Discussions focused on marimo’s development are conducted on a [Discord Server](https://marimo.io/discord?ref=governance). The server is public but requires email verification.

The server consists of several channels with different permissions based on the
concept of Discord roles. The named roles are “Project Maintainer” and
“Contributor.” The Project Maintainers have write access to all channels and
also have a private channel.

Individuals who have contributed significantly to the development of marimo,
for example by proposing and merging at least one substantial pull request, may
be invited to the Discord server as Contributors. Project Maintainers may grant
the Contributor role within Discord at their discretion, and may create
additional channels for specific long-term projects in marimo’s development.

### **Developer Calls**

The Steering Committee hosts semiannual developer calls to discuss
marimo-related business.

The precise time of a given call is determined one month ahead of time by discussions on the "developer-calls" channel of the marimo Discord Server.

### **Contributor License Agreement**

All contributors to marimo must sign a Contributor License Agreement (CLA) before their contributions can be accepted. The CLA is a legal agreement that assigns copyright of contributions to Marimo Inc. This helps protect the project and its users by ensuring clear ownership and licensing of all contributions.

The CLA can be found at <https://marimo.io/cla> and must be signed before any pull requests can be merged.
