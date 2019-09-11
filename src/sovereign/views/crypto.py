import jsonschema
from quart import Blueprint, request, jsonify, g
from sovereign.utils.crypto import encrypt, decrypt, generate_key

blueprint = Blueprint('crypto', __name__)

schema = {
    'title': 'Encryption parameter schema',
    "type": "object",
    'required': [
        'data'
    ],
    "properties": {
        'data': {
            'description': 'Data to be encrypted/decrypted.',
            'type': 'string',
            'minLength': 1,
            'maxLength': 65535
        },
        'key': {
            'description': 'Secret key to use when encrypting/decrypting. '
                           'Default is the applications own key, unless decrypting.',
            'type': 'string',
            'minLength': 44,
            'maxLength': 44
        }
    }
}


@blueprint.route('/crypto')
@blueprint.route('/crypto/help')
def _help():
    return jsonify(schema)


@blueprint.route('/crypto/decrypt', methods=['POST'])
async def _decrypt():
    req = await request.get_json(force=True)
    jsonschema.validate(req, schema)
    try:
        ret = {
            'result': decrypt(req['data'], req['key'])
        }
        code = 200
    except KeyError:
        ret = {
            'error': 'A key must be supplied to use for decryption'
        }
        code = 400
    return jsonify(ret), code


@blueprint.route('/crypto/encrypt', methods=['POST'])
async def _encrypt():
    req = await request.get_json(force=True)
    jsonschema.validate(req, schema)
    ret = {
        'result': encrypt(**req)
    }
    return jsonify(ret)


@blueprint.route('/crypto/decryptable', methods=['POST'])
async def _decryptable():
    req = await request.get_json(force=True)
    jsonschema.validate(req, schema)
    try:
        decrypt(req['data'])
        ret = {}
        code = 200
    except KeyError as e:
        ret = {
            'error': str(e),
            'request_id': g.request_id
        }
        code = 500
    return jsonify(ret), code


@blueprint.route('/crypto/generate_key')
def _generate_key():
    ret = {
        'result': generate_key()
    }
    return jsonify(ret)


@blueprint.errorhandler(jsonschema.SchemaError)
def schema_handler(exception):
    error = {
        'error': f'There was a problem with the server\'s schema.',
        'request_id': g.request_id
    }
    g.log = g.log.bind(**error, exception=repr(exception))
    return jsonify(error), 500


@blueprint.errorhandler(jsonschema.ValidationError)
def validation_handler(e: jsonschema.ValidationError):
    error = {
        'error': f'{e.__class__.__name__}: {e.message}',
        'request_id': g.request_id
    }
    g.log = g.log.bind(**error)
    return jsonify(error), 400
