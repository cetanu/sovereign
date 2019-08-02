.. _encryption:


Serving private data
--------------------
Sovereign comes with in-built encryption capabilities that allow the safe storage of objects such
as private keys, certificates, and any other data that may be considered confidential.


Configuring Sovereign with an encryption key
''''''''''''''''''''''''''''''''''''''''''''
On startup, Sovereign looks for a Fernet key in the environment variable ``SOVEREIGN_ENCRYPTION_KEY``.

You can generate a new key by starting Sovereign and accessing the ``/crypto/generate_key`` endpoint.

Example:

.. code-block:: none

    $ curl http://<sovereign>/crypto/generate_key
    {
        "result": "KjDxQrHuNrPRHICv1Qef6Sr_XHxsv7oarJdwB98R2wk="
    }

The resulting key should be placed into the environment variable.

.. danger::
   This key can be used to decrypt anything that you encrypt from this point onward.
   Ensure that the key is stored somewhere safe, such as LastPass, or some other secret/password vault.


Encrypting data so it can be stored as configuration
''''''''''''''''''''''''''''''''''''''''''''''''''''
Once you've placed your new Fernet key in the environment variable, and started Sovereign, it is now able to encrypt
and decrypt data for use in discovery requests/responses.

.. warning::
    Requests to Sovereign to encrypt data should be made over HTTPS to avoid third-parties potentially
    seeing what you are encrypting while it is in-flight.
    If your service does not have HTTPS/TLS, then you can run Sovereign locally and make the same requests.

.. code-block:: none

    $ curl -x POST http://<sovereign>/crypto/encrypt -d '{"data":"secrets"}'
    {
        "result": "gAAAAABbuuoUEGYQSZgUwWD7pE4xo7IPvTdkZ7CwxzvKG5rh_SOc1j0OmvjvcqAUvYHoMzy2J4kJsknMZupKsZW0pHIZD-Ldeg=="
    }

Encrypting certificates
'''''''''''''''''''''''
Possibly the most common thing that will need to be encrypted for your envoy proxies will be private keys.

Building on the above example, you may be able to easily encrypt a certificate by concatenating it into the JSON body
that is required for the ``/crypt/encrypt`` endpoint:

.. code-block:: none

    $ curl -X POST http://<sovereign>/crypto/encrypt -d "{\"data\": \"$(cat certificate.crt)\"}"


Verifying encrypted blocks of data to ensure they can be decrypted by your control-plane
''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
It may be wise as part of your sovereign deployment, to check whether all the encrypted data in your configuration is
valid.

You can do this using the following endpoint, which will use sovereigns private key to decrypt the data in order to
verify that is *can* be decrypted, but will not emit or return the data anywhere.

.. code-block:: none

    $ curl -x POST http://<sovereign>/crypto/decryptable -d '{"data":"gAAAAABbuuoUEGYQSZgUwWD7pE4xo7IPvTdkZ7CwxzvKG5rh_SOc1j0OmvjvcqAUvYHoMzy2J4kJsknMZupKsZW0pHIZD-Ldeg=="}'

This will result in a 200 OK response if the data was successfully decrypted, or a 500 otherwise.
