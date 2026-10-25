=====================================
POS Kitchen Direct Print (jIotBox)
=====================================

Purpose
========

This Odoo Point of Sale addon adds a preparation printer type named
**Direct print (jIotBox)**. Kitchen tickets are rendered in the browser as
raster images and sent to a jIotBox local HTTP agent, which relays them to a
local or USB printer. No Odoo IoT Box is required.

It also provides an optional jIotBox URL for customer receipts.

Requirements
============

* Odoo 19 Community Edition with the **Point of Sale** module installed.
* jIotBox installed and reachable from the Point of Sale terminal.
* HTTPS is recommended. The browser must allow the connection to the local
  agent, including its certificate when a self-signed certificate is used.
* Preparation printers can be restricted to product categories through the
  standard **Printed Product Categories** field.

Installation
============

#. Copy or install the ``pos_kitchen_direct_print`` addon in your Odoo addons
   path.
#. Update the apps list and install **POS Kitchen Direct Print (jIotBox)**.
#. Open **Point of Sale > Configuration > Preparation Printers** to configure
   kitchen printers.

Configuration
=============

Preparation printer
-------------------

#. Create or edit a preparation printer.
#. Select **Direct print (jIotBox)** as the printer type.
#. Enter the jIotBox agent URL, for example
   ``https://192.168.1.50:8443``. A base path such as
   ``https://192.168.1.50:8443/kitchen`` can be used when a reverse proxy
   forwards that prefix to the jIotBox agent; the action endpoint is appended
   to the configured URL.
#. Assign the product categories that this printer should print.

Customer receipt
----------------

#. Open the Point of Sale settings and select a Point of Sale.
#. In the **ePos Printer** section, enter the optional jIotBox receipt URL,
   for example ``https://192.168.1.50:8443/receipt``.
#. When both a jIotBox receipt URL and an Epson printer IP are configured, the
   settings form warns that jIotBox is used for the customer receipt instead
   of the Epson printer.

Architecture
============

* The Point of Sale renders kitchen tickets as raster images in the browser.
* Images are sent to the jIotBox agent through its local HTTP interface.
* The agent forwards the image to the configured local or USB printer.
* The client-side queue is cleared when a print request fails, so a failed
  request does not silently duplicate tickets on retry.
* Connection and printing errors are reported to the Point of Sale cashier.
* No server-side network call is made by Odoo; the browser communicates with
  the local agent only.

Security and network notes
==========================

* Prefer HTTPS. A page served over HTTPS cannot call a plain HTTP agent
  without triggering mixed-content blocking.
* Self-signed certificates must be trusted by the terminal browser or
  explicitly accepted by the user.
* URLs are validated and normalized on the server: only HTTP and HTTPS are
  accepted, credentials, query strings, fragments and control characters are
  rejected, and the length is limited.
* Odoo never fetches the jIotBox URL itself and stores no credentials for it.

Known limitations
=================

* A browser cannot access a USB printer directly; jIotBox (or an equivalent
  local agent) is required.
* Printing depends on the availability and configuration of the local
  jIotBox agent and its network route from the terminal.
* The optional customer receipt URL is used instead of the Epson printer when
  both are configured.

License
========

This module is licensed under **LGPL-3**. It is a clean-room implementation
and does not contain proprietary or OPL-licensed code.
