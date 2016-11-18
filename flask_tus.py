from flask import request, jsonify, make_response, current_app
import base64
import os
import redis
import uuid

# Find the stack on which we want to store the database connection.
# Starting with Flask 0.9, the _app_ctx_stack is the correct one,
# before that we need to use the _request_ctx_stack.
try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack

class tus_manager(object):

    def __init__(self, app=None, upload_url='/file-upload', upload_folder='uploads/', overwrite=True, upload_finish_cb=None):
        self.app = app
        if app is not None:
            self.init_app(app, upload_url, upload_folder, overwrite=overwrite, upload_finish_cb=upload_finish_cb)

    def init_app(self, app, upload_url='/file-upload', upload_folder='uploads/', overwrite=True, upload_finish_cb=None):

        self.upload_url = upload_url
        self.upload_folder = upload_folder
        self.tus_api_version = '1.0.0'
        self.tus_api_version_supported = '1.0.0'
        self.tus_api_extensions = ['creation', 'termination', 'file-check']
        self.tus_max_file_size = 4294967296 # 4GByte
        self.file_overwrite = overwrite
        self.upload_finish_cb = upload_finish_cb
        self.upload_file_handler_cb = None

        # register the two file upload endpoints
        app.add_url_rule(self.upload_url, 'file-upload', self.tus_file_upload, methods=['OPTIONS', 'POST', 'GET'])
        app.add_url_rule('{}/<resource_id>'.format( self.upload_url ), 'file-upload-chunk', self.tus_file_upload_chunk, methods=['HEAD', 'PATCH', 'DELETE'])


    def upload_file_handler( self, callback ):
        self.upload_file_handler_cb = callback
        return callback

    # handle redis server connection
    def redis_connect(self):
        return redis.Redis()

    @property
    def redis_connection(self):
        ctx = stack.top
        if ctx is not None:
            if not hasattr(ctx, 'tus_redis'):
                ctx.tus_redis = self.redis_connect()
            return ctx.tus_redis

    def tus_file_upload(self):

        response = make_response("", 200)

        if request.method == 'GET':
            metadata = {}
            for kv in request.headers.get("Upload-Metadata", None).split(","):
                (key, value) = kv.split(" ")
                metadata[key] = base64.b64decode(value)

            if metadata.get("filename", None) is None:
                return make_response("metadata filename is not set", 404)

            (filename_name, extension) = os.path.splitext( metadata.get("filename"))
            if filename_name.upper() in [os.path.splitext(f)[0].upper() for f in os.listdir( os.path.dirname( self.upload_folder ))]:
                response.headers['Tus-File-Name'] = metadata.get("filename")
                response.headers['Tus-File-Exists'] = True
            else:
                response.headers['Tus-File-Exists'] = False
            return response

        elif request.method == 'OPTIONS' and request.headers.get('Access-Control-Request-Method', None) is not None:
            # CORS option request, return 200
            return response

        if request.headers.get("Tus-Resumable") is not None:
            response.headers['Tus-Resumable'] = self.tus_api_version
            response.headers['Tus-Version'] = self.tus_api_version_supported

            if request.method == 'OPTIONS':
                response.headers['Tus-Extension'] = ",".join(self.tus_api_extensions)
                response.headers['Tus-Max-Size'] = self.tus_max_file_size

                response.status_code = 204
                return response

            # process upload metadata
            metadata = {}
            for kv in request.headers.get("Upload-Metadata", None).split(","):
                (key, value) = kv.split(" ")
                metadata[key] = base64.b64decode(value)

            if os.path.lexists( os.path.join( self.upload_folder, metadata.get("filename") )) and self.file_overwrite is False:
                response.status_code = 409
                return response

            file_size = int(request.headers.get("Upload-Length", "0"))
            resource_id = str(uuid.uuid4())

            p = self.redis_connection.pipeline()
            p.setex("file-uploads/{}/filename".format(resource_id), "{}".format(metadata.get("filename")), 3600)
            p.setex("file-uploads/{}/file_size".format(resource_id), file_size, 3600)
            p.setex("file-uploads/{}/offset".format(resource_id), 0, 3600)
            p.setex("file-uploads/{}/upload-metadata".format(resource_id), request.headers.get("Upload-Metadata"), 3600)
            p.execute()

            try:
                f = open( os.path.join( self.upload_folder, resource_id ), "wb")
                f.seek( file_size - 1)
                f.write("\0")
                f.close()
            except IOError as e:
                self.app.logger.error("Unable to create file: {}".format(e))
                response.status_code = 500
                return response

            response.status_code = 201
            response.headers['Location'] = '{}/{}/{}'.format(request.url_root, self.upload_url, resource_id)
            response.headers['Tus-Temp-Filename'] = resource_id
            response.autocorrect_location_header = False

        else:
            self.app.logger.warning("Received File upload for unsupported file transfer protocol")
            response.data = "Received File upload for unsupported file transfer protocol"
            response.status_code = 500

        return response

    def tus_file_upload_chunk(self, resource_id):
        response = make_response("", 204)
        response.headers['Tus-Resumable'] = self.tus_api_version
        response.headers['Tus-Version'] = self.tus_api_version_supported

        offset = self.redis_connection.get("file-uploads/{}/offset".format( resource_id ))
        upload_file_path = os.path.join( self.upload_folder, resource_id )

        if request.method == 'HEAD':
            offset = self.redis_connection.get("file-uploads/{}/offset".format( resource_id ))
            if offset is None:
                response.status_code = 404
                return response

            else:
                response.status_code = 200
                response.headers['Upload-Offset'] = offset
                response.headers['Cache-Control'] = 'no-store'

                return response

        if request.method == 'DELETE':
            os.unlink( upload_file_path )

            p = self.redis_connection.pipeline()
            p.delete("file-uploads/{}/filename".format(resource_id))
            p.delete("file-uploads/{}/file_size".format(resource_id))
            p.delete("file-uploads/{}/offset".format(resource_id))
            p.delete("file-uploads/{}/upload-metadata".format(resource_id))
            p.execute()

            response.status_code = 204
            return respose
        
        if request.method == 'PATCH':
            filename = self.redis_connection.get("file-uploads/{}/filename".format( resource_id ))
            if filename is None or os.path.lexists( upload_file_path ) is False:
                self.app.logger.info( "PATCH sent for resource_id that does not exist. {}".format( resource_id))
                response.status_code = 410
                return response

            file_offset = int(request.headers.get("Upload-Offset", 0))
            chunk_size = int(request.headers.get("Content-Length", 0))
            file_size = int( self.redis_connection.get( "file-uploads/{}/file_size".format( resource_id )) )

            if request.headers.get("Upload-Offset") != self.redis_connection.get( "file-uploads/{}/offset".format( resource_id )): # check to make sure we're in sync
                response.status_code = 409 # HTTP 409 Conflict
                return response

            try:
                f = open( upload_file_path, "r+b")
            except IOError:
                f = open( upload_file_path, "wb")
            finally:
                f.seek( file_offset )
                f.write(request.data)
                f.close()

            new_offset = self.redis_connection.incrby( "file-uploads/{}/offset".format( resource_id ), chunk_size)
            response.headers['Upload-Offset'] = new_offset
            response.headers['Tus-Temp-Filename'] = resource_id

            if file_size == new_offset: # file transfer complete, rename from resource id to actual filename
                if self.upload_file_handler_cb is None:
                    os.rename( upload_file_path, os.path.join( self.upload_folder, filename ))
                else:
                    filename = self.upload_file_handler_cb( upload_file_path, filename ) 

                p = self.redis_connection.pipeline()
                p.delete("file-uploads/{}/filename".format(resource_id))
                p.delete("file-uploads/{}/file_size".format(resource_id))
                p.delete("file-uploads/{}/offset".format(resource_id))
                p.delete("file-uploads/{}/upload-metadata".format(resource_id))
                p.execute()

                if self.upload_finish_cb is not None:
                    self.upload_finish_cb()

            return response
