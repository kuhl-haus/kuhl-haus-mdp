.. image:: https://img.shields.io/github/license/kuhl-haus/kuhl-haus-mdp
    :alt: License
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/blob/mainline/LICENSE.txt
.. image:: https://img.shields.io/pypi/v/kuhl-haus-mdp.svg
    :alt: PyPI
    :target: https://pypi.org/project/kuhl-haus-mdp/
.. image:: https://static.pepy.tech/badge/kuhl-haus-mdp/month
    :alt: Downloads
    :target: https://pepy.tech/project/kuhl-haus-mdp
.. image:: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml/badge.svg
    :alt: Build Status
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml
.. image:: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/codeql.yml/badge.svg
    :alt: CodeQL Advanced
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/codeql.yml
.. image:: https://codecov.io/gh/kuhl-haus/kuhl-haus-mdp/branch/mainline/graph/badge.svg
    :alt: codecov
    :target: https://codecov.io/gh/kuhl-haus/kuhl-haus-mdp
.. image:: https://img.shields.io/github/issues/kuhl-haus/kuhl-haus-mdp
    :alt: GitHub issues
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/issues
.. image:: https://img.shields.io/github/issues-pr/kuhl-haus/kuhl-haus-mdp
    :alt: GitHub pull requests
    :target: https://github.com/kuhl-haus/kuhl-haus-mdp/pulls
.. image:: https://readthedocs.org/projects/kuhl-haus-mdp/badge/?version=latest
    :alt: Documentation
    :target: https://kuhl-haus-mdp.readthedocs.io/en/latest/

|

==============
kuhl-haus-mdp
==============

Market data processing library.

Overview
========

The Kuhl Haus Market Data Platform (MDP) is a distributed system for collecting, processing, and serving real-time market data. Built on Kubernetes and leveraging microservices architecture, MDP provides scalable infrastructure for financial data analysis and visualization.

Key Features
------------

- Real-time market data ingestion and processing
- Scalable microservices architecture
- Automated deployment with Ansible and Kubernetes
- Multi-environment support (development, staging, production)
- OAuth integration for secure authentication
- Redis-based caching layer for performance

Code Organization
-----------------

The platform consists of four main packages:

- **Market data processing library** (`kuhl-haus-mdp <https://github.com/kuhl-haus/kuhl-haus-mdp>`_) - Core library with shared data processing logic
- **Backend Services** (`kuhl-haus-mdp-servers <https://github.com/kuhl-haus/kuhl-haus-mdp-servers>`_) - Market data listener, processor, and widget service
- **Frontend Application** (`kuhl-haus-mdp-app <https://github.com/kuhl-haus/kuhl-haus-mdp-app>`_) - Web-based user interface and API
- **Deployment Automation** (`kuhl-haus-mdp-deployment <https://github.com/kuhl-haus/kuhl-haus-mdp-deployment>`_) - Docker Compose, Ansible playbooks and Kubernetes manifests for environment provisioning

Documentation
-------------

For architecture details, component descriptions, and API reference, see the
`full documentation on Read the Docs <https://kuhl-haus-mdp.readthedocs.io/en/latest/>`_.

Additional Resources
--------------------

📖 **Blog Series:**

- `Part 1: Why I Built It <https://oldschool-engineer.dev/side%20projects/2026/01/16/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner.html>`_
- `Part 2: How to Run It <https://oldschool-engineer.dev/side%20projects/2026/01/21/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-2.html>`_
- `Part 3: How to Deploy It <https://oldschool-engineer.dev/infrastructure/2026/01/31/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-3.html>`_
- `Part 4: Evolution from Prototype to Production <https://oldschool-engineer.dev/software%20engineering/2026/02/11/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-4.html>`_
- `Part 5: Wave 1 Complete: Bugs, Bottlenecks, and Breaking 1,000 msg/s <https://oldschool-engineer.dev/software%20engineering/2026/02/23/what-i-built-after-quitting-amazon-spoiler-its-a-stock-scanner-part-5.html>`_
- `Stock Selection: Why News Matters <https://oldschool-engineer.dev/side%20projects/2026/04/01/stock-selection-why-news-matters.html>`_
