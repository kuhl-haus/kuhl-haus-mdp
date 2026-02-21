============
Contributing
============

Welcome to ``kuhl-haus-mdp`` contributor's guide.

This document focuses on getting any potential contributor familiarized
with the development processes, but `other kinds of contributions`_ are also
appreciated.

If you are new to using git_ or have never collaborated in a project previously,
please have a look at `contribution-guide.org`_. Other resources are also
listed in the excellent `guide created by FreeCodeCamp`_ [#contrib1]_.

Please notice, all users and contributors are expected to be **open,
considerate, reasonable, and respectful**. When in doubt, `Python Software
Foundation's Code of Conduct`_ is a good reference in terms of behavior
guidelines.


Issue Reports
=============

If you experience bugs or general issues with ``kuhl-haus-mdp``, please have a look
on the `issue tracker`_. If you don't see anything useful there, please feel
free to fire an issue report.

.. tip::
   Please don't forget to include the closed issues in your search.
   Sometimes a solution was already reported, and the problem is considered
   **solved**.

New issue reports should include information about your programming environment
(e.g., operating system, Python version) and steps to reproduce the problem.
Please try also to simplify the reproduction steps to a very minimal example
that still illustrates the problem you are facing. By removing other factors,
you help us to identify the root cause of the issue.


Documentation Improvements
==========================

You can help improve ``kuhl-haus-mdp`` docs by making them more readable and coherent, or
by adding missing information and correcting mistakes.

``kuhl-haus-mdp`` documentation uses Sphinx_ as its main documentation compiler
with reStructuredText_ markup. The docs live in the ``docs`` directory alongside
the project code, and any documentation update follows the same workflow as a
code contribution.

To build the documentation locally, use one of the provided scripts from the
project root (there are also PyCharm run configurations for this).

**Linux / macOS:**

.. code-block:: bash

   ./build-docs.sh
   ./build-docs.sh --clean

**Windows:**

.. code-block:: powershell

   .\Build-Docs.ps1
   .\Build-Docs.ps1 -Clean

Both scripts generate HTML output in ``docs/_build/html`` and open
``index.html`` in the default browser. The ``--clean`` / ``-Clean`` flag wipes
previous build output first.


Code Contributions
==================

Before diving in, please review the README_ for an overview of the system
architecture, component descriptions, and data flow. The `API documentation`_
(generated from docstrings) is also a helpful reference.

Submit an issue
---------------

Before you work on any non-trivial code contribution it's best to first create
a report in the `issue tracker`_ to start a discussion on the subject.
This often provides additional considerations and avoids unnecessary work.

Clone the repository
--------------------

#. Create a user account on GitHub_ if you do not already have one.
#. Fork the project repository_: click on the *Fork* button near the top of the
   page. This creates a copy of the code under your account on GitHub.
#. Clone this copy to your local disk::

    git clone git@github.com:YourLogin/kuhl-haus-mdp.git
    cd kuhl-haus-mdp

Create an environment
---------------------

This project uses PDM_ for builds and requires **Python 3.14** or later.

#. Create and activate a Python virtual environment:

   **Linux / macOS:**

   .. code-block:: bash

      python3 -m venv .venv
      source .venv/bin/activate

   **Windows:**

   .. code-block:: powershell

      python -m venv .venv
      .venv\Scripts\Activate.ps1

#. Install the project's dependencies::

    pip install -r requirements.txt

#. Install the project's test dependencies::

    pip install -r requirements-test.txt

Implement your changes
----------------------

#. Create a branch to hold your changes::

    git checkout -b my-feature

   and start making changes. Never work on the main branch!

#. Start your work on this branch. Don't forget to add docstrings_ to new
   functions, modules and classes, especially if they are part of public APIs.

#. Add yourself to the list of contributors in ``AUTHORS.rst``.

#. When you're done editing, do::

    git add <MODIFIED FILES>
    git commit

   to record your changes in git_.

   .. important:: Don't forget to add unit tests and documentation in case your
      contribution adds an additional feature and is not just a bugfix.

      Moreover, writing a `descriptive commit message`_ is highly recommended.
      In case of doubt, you can check the commit history with::

         git log --graph --decorate --pretty=oneline --abbrev-commit --all

      to look for recurring communication patterns.

#. Run the unit tests with coverage to make sure nothing is broken::

    pdm run pytest --cov=kuhl_haus.mdp --cov-report=html tests -v

   This produces an HTML coverage report in ``htmlcov/``.

#. Run flake8_ to check code style::

    flake8 src/kuhl_haus/mdp --count --select=E9,F63,F7,F82 --show-source --statistics
    flake8 src/kuhl_haus/mdp --count --exit-zero --ignore=C901,W503 --max-complexity=10 --max-line-length=127 --statistics


Submit your contribution
------------------------

#. If everything works fine, push your local branch to GitHub with::

    git push -u origin my-feature

#. Go to the web page of your fork and click "Create pull request"
   to send your changes for review.

Troubleshooting
---------------

The following tips can be used when facing problems to build or test the
package:

#. Make sure to fetch all the tags from the upstream repository_.
   The command ``git describe --abbrev=0 --tags`` should return the version you
   are expecting. If you are trying to run CI scripts in a fork repository,
   make sure to push all the tags.
   You can also try to remove all the egg files or the complete egg folder, i.e.,
   ``.eggs``, as well as the ``*.egg-info`` folders in the ``src`` folder or
   potentially in the root of your project.

#. `Pytest can drop you`_ in an interactive session in the case an error occurs.
   In order to do that you need to pass a ``--pdb`` option (for example by
   running ``pdm run pytest -k <NAME OF THE FAILING TEST> --pdb``).
   You can also setup breakpoints manually instead of using the ``--pdb`` option.


Maintainer tasks
================

Releases
--------

If you are part of the group of maintainers and have correct user permissions
on PyPI_, the following steps can be used to release a new version for
``kuhl-haus-mdp``:

#. Make sure all workflows for the latest commit are successful.
#. Run the `release-workflow`_ to generate release notes.
#. After reviewing the release notes, tag the commit on the mainline branch with a corresponding release tag, e.g., ``v1.2.3``.
#. Push the new tag to the upstream repository_, e.g., ``git push upstream v1.2.3``
#. The `publish-to-pypi`_ GitHub Actions workflow will build and upload the
   package automatically.


.. [#contrib1] Even though, these resources focus on open source projects and
   communities, the general ideas behind collaborating with other developers
   to collectively create software are general and can be applied to all sorts
   of environments, including private companies and proprietary code bases.


.. _repository: https://github.com/kuhl-haus/kuhl-haus-mdp
.. _issue tracker: https://github.com/kuhl-haus/kuhl-haus-mdp/issues
.. _publish-to-pypi: https://github.com/kuhl-haus/kuhl-haus-mdp/actions/workflows/publish-to-pypi.yml
.. _release-workflow: https://github.com/kuhl-haus/kuhl-haus-mdp/blob/mainline/.github/workflows/release.yml

.. _API documentation: https://kuhl-haus-mdp.readthedocs.io/en/latest/
.. _README: https://github.com/kuhl-haus/kuhl-haus-mdp/blob/mainline/README.rst

.. _contribution-guide.org: https://www.contribution-guide.org/
.. _creating a PR: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request
.. _descriptive commit message: https://chris.beams.io/posts/git-commit
.. _docstrings: https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html
.. _flake8: https://flake8.pycqa.org/en/stable/
.. _git: https://git-scm.com
.. _GitHub: https://github.com
.. _guide created by FreeCodeCamp: https://github.com/FreeCodeCamp/how-to-contribute-to-open-source
.. _other kinds of contributions: https://opensource.guide/how-to-contribute
.. _PDM: https://pdm-project.org/
.. _Pytest can drop you: https://docs.pytest.org/en/stable/how-to/failures.html#using-python-library-pdb-with-pytest
.. _Python Software Foundation's Code of Conduct: https://www.python.org/psf/conduct/
.. _PyPI: https://pypi.org/
.. _reStructuredText: https://www.sphinx-doc.org/en/master/usage/restructuredtext/
.. _Sphinx: https://www.sphinx-doc.org/en/master/
