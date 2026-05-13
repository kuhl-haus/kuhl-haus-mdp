.. _troubleshooting-layout-recovery-v041:

Recovering Dashboard Layouts After Upgrading to v0.4.1
=======================================================

.. note::

   This article applies to the **front-end application**
   (`kuhl-haus-mdp-app <https://github.com/kuhl-haus/kuhl-haus-mdp-app>`_),
   not the core library (`kuhl-haus-mdp <https://github.com/kuhl-haus/kuhl-haus-mdp>`_).
   All Kuhl Haus MDP documentation is published here because
   `kuhl-haus-mdp` is the only repository with a Read the Docs subscription.

The only visible changes from v0.4.0 to v0.4.1 are UI elements to control
audio alerts on the Range Alerts and News Feed widgets. Under the hood, local
storage got a complete overhaul. Unfortunately, this means breaking changes,
but it is better to do it now than later.

**Here's what breaks:** All your existing dashboard settings will be reset.

There's no automatic migration. There's no script. However, the dashboard has
a built-in export function.


Before Upgrading
----------------

Before upgrading:

1. Click **📤 Export** in the toolbar.
2. Save the downloaded ``dashboard-layouts-<timestamp>.json`` file somewhere.


After Upgrading
---------------

After upgrading, click **📥 Import** and select that file. The exported format
is exactly the import format — nothing else required.

.. tip::

   Export before any upgrade, full stop. The export is a clean snapshot of
   everything — layout configurations, widget positions, column counts,
   descriptions, and your default layout. It's a 1-second operation.


Remediations
------------

If you already upgraded and found your layouts are gone, you have two options:

1. Rollback to the previous image. The application will read from the
   ``dashboard-layouts`` key and you can follow the export procedure above.
2. Copy the ``dashboard-layouts`` key using DevTools and create a specially
   formatted JSON file for importing. (More details provided below.)


What Happened
-------------

Starting with **v0.4.1**, the Stock Scanner Dashboard moved its layout storage
from plain localStorage keys to a `Pinia <https://pinia.vuejs.org/>`_ store
managed by ``pinia-plugin-persistedstate``
(`#278 <https://github.com/kuhl-haus/kuhl-haus-mdp-app/issues/278>`_).

The precise breaking point is commit ``e0c0d7c`` — **12 commits into the
v0.4.1 development cycle** (``v0.4.1.dev12-e0c0d7c``). Before that commit,
the dashboard read and wrote four separate localStorage keys:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Key
     - What it stored
   * - ``dashboard-layouts``
     - All saved layouts (the big one)
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


Recovery Procedure
------------------

The recovery is a two-step process: extract the raw layout data from the old
key, wrap it in the dashboard's import format, then import it through the UI.

**Step 1 — Open your browser's DevTools and find the old key**

Desktop (Chrome, Firefox, Edge):

1. Open the dashboard in your browser.
2. Open DevTools:

   - Chrome/Edge: ``F12`` or ``Cmd+Opt+I`` (Mac) / ``Ctrl+Shift+I`` (Windows/Linux)
   - Firefox: ``F12`` or ``Ctrl+Shift+I``

3. Go to the **Application** tab (Chrome/Edge) or **Storage** tab (Firefox).
4. In the left sidebar, expand **Local Storage** and click your site's origin
   (e.g. ``https://mdp.example.com`` or ``http://localhost:8000``).
5. Find the row with Key = ``dashboard-layouts``.

You should see a JSON object in the Value column that looks something like
this::

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

6. **Copy the entire value** — everything including the opening ``{`` and the
   closing ``}``.

.. note::

   If ``dashboard-layouts`` is missing or empty, your layouts were already
   gone before the upgrade, or you're on a fresh install. Unfortunately
   there's nothing to recover.

**Step 2 — Pick your default layout name**

While you still have DevTools open, take note of the layout name in the
``dashboard-default-layout`` key. You'll need it in the next step. It must
match a key in the JSON you just copied — spelling and capitalization must be
exact.

**Step 3 — Build the import file**

Create a new file called ``layout-recovery.json`` (the filename doesn't
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

- The ``version`` field must be ``1``.
- The ``exported`` timestamp is metadata only — the import ignores it. Use any
  number.
- ``defaultLayout`` is optional; if the name doesn't match a key in
  ``layouts``, it's silently ignored.
- The import **merges** into whatever layouts already exist — it won't wipe
  anything. If a name conflicts, you'll be prompted to confirm overwrite.

**Step 4 — Import through the dashboard UI**

1. Click the **📥 Import** button in the toolbar.
2. Select your ``layout-recovery.json`` file.
3. Confirm the overwrite prompt if one appears.
4. You should see an alert: *"Imported N layout(s)"*.
5. Your layouts are back.


Recovery on iPad (Safari + iOS)
--------------------------------

Mobile browsers don't expose a DevTools UI, so the procedure above doesn't
work directly. On iOS, you can access the full Safari DevTools remotely from
a Mac.

**What you need**

- Your iPad running the dashboard in Safari.
- A Mac with Safari.
- A **USB cable** (Lightning to USB-C or USB-C to USB-C, depending on your iPad and Mac model).
  Wi-Fi pairing works in theory, but USB is more reliable.

**Step 1 — Enable Web Inspector on your iPad**

On iPad: **Settings** → **Safari** → **Advanced** → toggle **Web Inspector** ON.

See also: `Inspecting iOS with Safari DevTools
<https://developer.apple.com/documentation/safari-developer-tools/inspecting-ios>`_

**Step 2 — Enable the Develop menu in Safari on your Mac**

On Mac: **Safari** → **Settings** (or Preferences) → **Advanced** tab →
check **"Show features for web developers"** (or "Show Develop menu in menu
bar" in older Safari versions).

See also: `Enabling Developer Features in Safari
<https://developer.apple.com/documentation/safari-developer-tools/enabling-developer-features>`_

**Step 3 — Connect and inspect**

1. Connect your iPad to your Mac with the USB cable. Trust the computer if
   prompted on the iPad.
2. On your iPad, open Safari and navigate to your dashboard. **Keep the tab
   open and active.**
3. On your Mac in Safari: **Develop** menu → your iPad's name → your
   dashboard tab.
4. The full Web Inspector opens on your Mac, pointing at the page running on
   your iPad.

From here, the procedure is identical to desktop:

- Go to **Storage** → **Local Storage** → find ``dashboard-layouts``.
- Copy the value, build the import JSON on your Mac, then either:

  - AirDrop the file to your iPad and import from there, or
  - Sync via iCloud and import from there.


Technical Appendix
------------------

**The new storage structure (v0.4.1+)**

For reference, the ``widgetSettings`` key now stores:

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

**Identifying the exact version**

If you're not sure whether your install crossed the breaking point, starting
with ``v0.4.0`` the version string is shown in the top-right corner of the
dashboard header (e.g. ``v0.4.1``). Any build at or after
``v0.4.1.dev12-e0c0d7c`` has the new storage layout. If you do not see a
version in the top-right corner then you are on a version earlier than
``v0.4.0``.
