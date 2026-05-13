.. _troubleshooting-layout-recovery-v041:

Recovering Dashboard Layouts After Upgrading to v0.4.1
=======================================================

The only visible changes from v0.4.0 to v0.4.1 are UI elements to control
audio alerts on the Range Alerts and News Feed widgets. Under the hood, local
storage got a complete overhaul. This means breaking changes — all existing
dashboard settings will be reset on upgrade.

There is no automatic migration and no script, but the dashboard has a
built-in export function that makes recovery straightforward.


Before Upgrading
----------------

If you have not upgraded yet, export your layouts first:

1. Click **📤 Export** in the toolbar.
2. Save the downloaded ``dashboard-layouts-<timestamp>.json`` file somewhere safe.

After upgrading, click **📥 Import** and select that file. The exported format
is exactly the import format — nothing else required.

.. tip::

   Export before every upgrade. The export captures layout configurations,
   widget positions, column counts, descriptions, and your default layout.
   It is a one-second operation.


If You Already Upgraded
-----------------------

You have two options:

1. **Roll back** to the previous image. The app will read from the old
   ``dashboard-layouts`` key and you can follow the export procedure above
   before upgrading again.

2. **Recover manually** using browser DevTools. Full procedure below.


What Happened
-------------

Starting with **v0.4.1**, the Stock Scanner Dashboard moved its layout storage
from plain localStorage keys to a `Pinia <https://pinia.vuejs.org/>`_ store
managed by ``pinia-plugin-persistedstate``
(`#278 <https://github.com/kuhl-haus/kuhl-haus-mdp-app/issues/278>`_).

The precise breaking point is commit ``e0c0d7c`` — 12 commits into the v0.4.1
development cycle. Before that commit, the dashboard read and wrote four
separate localStorage keys:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - What it stored
   * - ``dashboard-layouts``
     - All saved layouts
   * - ``dashboard-default-layout``
     - Name of the default layout
   * - ``dashboard-layout-locked``
     - Lock state (``"true"`` / ``"false"``)
   * - ``dashboard-autosave-enabled``
     - Autosave state (``"true"`` / ``"false"``)

After ``e0c0d7c``, all of that consolidated into a single key:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - What it stores
   * - ``widgetSettings``
     - A JSON object containing ``savedLayouts``, ``defaultLayoutName``,
       ``isLocked``, ``autosaveEnabled``, and additional widget preferences

When you upgrade, the app starts fresh under the new ``widgetSettings`` key.
**Your layouts are not gone** — they are still sitting in ``dashboard-layouts``
in localStorage exactly as you left them. The app just stopped looking there.


Recovery Procedure (Desktop)
-----------------------------

**Step 1 — Open DevTools and find the old key**

Open the dashboard in your browser, then open DevTools:

- **Chrome / Edge:** ``F12`` or ``Cmd+Opt+I`` (Mac) / ``Ctrl+Shift+I`` (Windows/Linux)
- **Firefox:** ``F12`` or ``Ctrl+Shift+I``

Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
In the left sidebar, expand **Local Storage** and click your site's origin
(e.g. ``https://mdp.kuhl.haus`` or ``http://localhost:4201``).

Find the row with Key = ``dashboard-layouts``. The value will be a JSON object
like this::

    {
      "My Trading Setup": {
        "layout": [...],
        "widgetCounter": 7,
        "dashboardColNum": 12,
        "created": 1746000000000,
        "modified": 1747000000000,
        "description": ""
      },
      "Scalp Setup": { ... }
    }

Copy the entire value — everything from the opening ``{`` to the closing ``}``.

.. note::

   If ``dashboard-layouts`` is missing or empty, your layouts were already
   gone before the upgrade, or you are on a fresh install. There is nothing
   to recover.

**Step 2 — Get your default layout name**

While DevTools is still open, look at the ``dashboard-default-layout`` key.
Copy the exact value — spelling and capitalization must match a key in the
``dashboard-layouts`` JSON you just copied.

**Step 3 — Build the import file**

Create a new file called ``layout-recovery.json`` (the filename does not
matter). Paste the following, substituting your values:

.. code-block:: json

    {
      "version": 1,
      "exported": 1778262561424,
      "layouts": <PASTE YOUR dashboard-layouts VALUE HERE>,
      "defaultLayout": "<EXACT NAME OF ONE OF YOUR LAYOUTS>"
    }

**Concrete example:**

.. code-block:: json

    {
      "version": 1,
      "exported": 1778262561424,
      "layouts": {
        "My Trading Setup": {
          "layout": [...],
          "widgetCounter": 7,
          "dashboardColNum": 12,
          "created": 1746000000000,
          "modified": 1747000000000,
          "description": ""
        },
        "Scalp Setup": { ... }
      },
      "defaultLayout": "My Trading Setup"
    }

A few things to know about this format:

- ``version`` must be ``1``.
- ``exported`` is metadata only — the import ignores it. Any number will do.
- ``defaultLayout`` is optional. If the name does not match a key in
  ``layouts``, it is silently ignored.
- The import **merges** into existing layouts. If a name conflicts, you will
  be prompted to confirm before overwriting.

**Step 4 — Import through the dashboard UI**

1. Click the **📥 Import** button in the toolbar.
2. Select your ``layout-recovery.json`` file.
3. Confirm the overwrite prompt if one appears.
4. You should see a confirmation: *"Imported N layout(s)"*.
5. Set your default in the layout dropdown and re-lock.


Recovery on iPad (Safari + iOS)
--------------------------------

Mobile browsers do not expose a DevTools UI locally. On iOS, you can access
the full Safari Web Inspector remotely from a Mac over USB.

**What you need**

- Your iPad running the dashboard in Safari.
- A Mac with Safari.
- A USB cable (Lightning or USB-C depending on your iPad model). Wi-Fi pairing
  works in theory, but USB is more reliable.

**Step 1 — Enable Web Inspector on your iPad**

On iPad: **Settings → Safari → Advanced → Web Inspector → ON**.

See also: `Inspecting iOS with Safari DevTools
<https://developer.apple.com/documentation/safari-developer-tools/inspecting-ios>`_

**Step 2 — Enable the Develop menu in Safari on your Mac**

On Mac: **Safari → Settings → Advanced → "Show features for web developers"**
(or "Show Develop menu in menu bar" in older Safari versions).

See also: `Enabling Developer Features in Safari
<https://developer.apple.com/documentation/safari-developer-tools/enabling-developer-features>`_

**Step 3 — Connect and inspect**

1. Connect your iPad to your Mac with the USB cable. Trust the computer if
   prompted on the iPad.
2. On your iPad, open Safari and navigate to your dashboard. Keep the tab open
   and active.
3. On your Mac in Safari: **Develop → your iPad's name → your dashboard tab**.
4. The full Web Inspector opens on your Mac, targeting the page on your iPad.

From here, the procedure is identical to desktop: find ``dashboard-layouts``
under **Storage → Local Storage**, copy the value, and build the import JSON
on your Mac. Then either:

- Sync the file via iCloud and import from your iPad, or
- Import directly from the Mac browser if the dashboard is accessible there.


Technical Appendix
------------------

**New storage structure (v0.4.1+)**

The ``widgetSettings`` key now stores:

.. code-block:: json

    {
      "savedLayouts": {
        "My Trading Setup": { ... }
      },
      "defaultLayoutName": "My Trading Setup",
      "isLocked": true,
      "autosaveEnabled": true,
      "maxArticles": 1000,
      "hasTickersOnly": false,
      "defaultAlertSound": "...",
      "alertManagerOpen": false
    }

After recovering, inspect this key in DevTools to confirm ``savedLayouts``
contains your layouts.

**Identifying the exact version**

Starting with v0.4.0, the version string is shown in the top-right corner of
the dashboard header (e.g. ``v0.4.1``). Any build at or after
``v0.4.1.dev12-e0c0d7c`` uses the new storage layout. If no version string is
visible, the install is older than ``v0.4.0`` and uses the old keys.
