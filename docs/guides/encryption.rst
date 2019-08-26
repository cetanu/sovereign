.. _encryption:


Serving private data
====================
Sovereign comes with in-built encryption capabilities that allow the safe storage of objects such
as private keys, certificates, and any other data that may be considered confidential.


Generating a private key
------------------------
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


Encrypting data
---------------
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

Now that your data is encrypted it can be safely stored as config for sovereign; for example we store encrypted
certificates in our version control server. You can see `example encrypted certificates`_ in the repo.

.. _example encrypted certificates: https://bitbucket.org/atlassian/sovereign/src/master/test/config/certificates.yaml#lines-49:86

Encrypting certificates
-----------------------
To follow on from the above example, one of the most common things that will need to be encrypted for your envoy proxies will be private keys.

You can encrypt a multiline string such as a private key by concatenating it into the JSON body that is required for the ``/crypt/encrypt`` endpoint:

.. code-block:: none

    $ curl -X POST http://<sovereign>/crypto/encrypt -d "{\"data\": \"$(cat certificate.crt)\"}"


Decrypting data in templates
----------------------------
By default, Sovereign makes its cryptographic tools available in templates. You can encrypt, decrypt, and generate new keys.

Example usage:

.. code-block:: jinja

    {% set secret = crypto.encrypt('helloworld') %}
    Encrypted: {{ secret }}
    Plaintext: {{ crypto.decrypt(secret) }}
    New fernet key: {{ crypto.generate_key() }}

I can't think of any reason why you might want to encrypt data or generate a key, but maybe you can.

The primary use-case within our company has been to decrypt private keys.

Verifying encrypted data
------------------------
It may be wise as part of your sovereign deployment, to check whether all the encrypted data in your configuration is
valid.

You can do this using the following endpoint, which will use sovereigns private key to decrypt the data in order to
verify that is *can* be decrypted, but will not emit or return the data anywhere.

.. code-block:: none

    $ curl -x POST http://<sovereign>/crypto/decryptable -d '{"data":"gAAAAABbuuoUEGYQSZgUwWD7pE4xo7IPvTdkZ7CwxzvKG5rh_SOc1j0OmvjvcqAUvYHoMzy2J4kJsknMZupKsZW0pHIZD-Ldeg=="}'

This will result in a 200 OK response if the data was successfully decrypted, or a 500 otherwise.
