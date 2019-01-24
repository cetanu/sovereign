Frequently Asked Questions
==========================

How can I configure the ASGI server?
------------------------------------

.. csv-table::
  :header: Environment Variable, Default, Description
  :widths: 1, 1, 2

    * ASGI_PORT,8080,Port for the server to bind to
    * ASGI_BIND,0.0.0.0,Socket for the server to bind to
    * ASGI_KEEPALIVE,5,How long to keep TCP sessions alive; specifying 0 disables keep-alives
