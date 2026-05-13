.. _troubleshooting-layout-recovery-v041:

Recovering Dashboard Layouts After Upgrading to v0.4.1
=======================================================

Starting with **v0.4.1**, the Stock Scanner Dashboard moved its layout storage
from plain localStorage keys to a `Pinia <https://pinia.vuejs.org/>`_ store
managed by ``pinia-plugin-persistedstate``. The breaking point is commit
``e0c0d7c`` — 12 commits into the v0.4.1 cycle.

Before that commit, the dashboard read and wrote four separate localStorage keys:

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
**Your layouts are not gone** — they're still sitting in ``dashboard-layouts``
in localStorage exactly as you left them. The app just stopped looking there.


Recovery Procedure (Desktop)
-----------------------------

The recovery is a two-step process: extract the raw layout data from the old
key, wrap it in the dashboard's import format, then import it through the UI.

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

   If ``dashboard-layouts`` is missing or empty, there is nothing to recover.
   This indicates a fresh install or that the layouts were lost prior to
   upgrading.

**Step 2 — Note your default layout name**

While DevTools is still open, note the exact spelling (including capitalization)
of the layout name you want to set as default. It must match a key in the JSON
you just copied.

**Step 3 — Build the import file**

Create a file named ``layout-recovery.json`` with the following structure,
substituting your values:

.. code-block:: json

    {
      "version": 1,
      "exported": 1778262561424,
      "layouts": <PASTE YOUR dashboard-layouts VALUE HERE>,
      "defaultLayout": "<EXACT NAME OF ONE OF YOUR LAYOUTS>"
    }

A few things to know about this format:

- ``version`` must be ``1``.
- ``exported`` is metadata only — the import ignores it. Any number will do.
- ``defaultLayout`` is optional. If the name doesn't match a key in
  ``layouts``, it is silently ignored.
- The import **merges** into existing layouts. If a name conflicts, you will
  be prompted to confirm before overwriting.

**Step 4 — Import through the dashboard UI**

1. Unlock the layout (click 🔒 in the toolbar — it should change to ✏️).
2. Click the **📥 Import** button in the toolbar.
3. Select your ``layout-recovery.json`` file.
4. Confirm the overwrite prompt if one appears.
5. You should see a confirmation: *"Imported N layout(s)"*.
6. Set your default in the layout dropdown and re-lock.


Recovery on iPad (Safari + iOS)
--------------------------------

Mobile Safari does not expose DevTools locally. You can access the full Web
Inspector remotely from a Mac over USB.

**What you need**

- Your iPad running the dashboard in Safari.
- A Mac with Safari.
- A USB cable (Lightning or USB-C depending on your iPad model).

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
under **Storage → Local Storage**, copy the value, build the import JSON on
your Mac, then either AirDrop the file to your iPad and import from there, or
import directly from the Mac browser if the dashboard is also accessible from
the Mac.


Avoiding This in the Future
----------------------------

The dashboard has a built-in export function. Before any upgrade:

1. Unlock the layout (🔒 → ✏️).
2. Click **📤 Export** in the toolbar.
3. Save the downloaded ``dashboard-layouts-<timestamp>.json`` file.

If something goes wrong after upgrading, click **📥 Import** and select that
file. The exported format is exactly the import format — no manual JSON
construction required.

.. tip::

   Export before every upgrade. The export captures layout configurations,
   widget positions, column counts, descriptions, and your default layout. It
   is a 10-second operation.


Technical Reference
-------------------

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

The version string is shown in the bottom-right corner of the dashboard header
(e.g. ``v0.4.1``). Any build at or after ``v0.4.1.dev12-e0c0d7c`` uses the
new storage layout. Any build at ``v0.4.0`` or earlier uses the old keys.
